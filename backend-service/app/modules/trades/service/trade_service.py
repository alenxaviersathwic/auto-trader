import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.exception.app_exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.core.pagination.page_result import PageResult
from app.modules.opportunities.service.costs import round_trip_cost_pct
from app.modules.opportunities.service.menu_builder import MOMO_EXIT
from app.modules.opportunities.service.setups import SETUP_POLICY
from app.modules.opportunities.service.run_service import opportunity_run_service
from app.modules.sessions.service.session_sizing import (
    MAX_ONE_LOT_RISK_PCT,
    RISK_PER_TRADE_PCT,
    correlated_block,
    entry_ceiling,
)
from app.modules.trades.entity.trade_entity import ActiveTrade
from app.modules.trades.repository.trade_repository import TradeRepository, trade_repository
from app.modules.trades.schema.trade_schema import (
    LotSuggestionResponse,
    TradeAdjustRequest,
    TradeCreateRequest,
    TradeExitRequest,
    TradeLiveSnapshot,
    TradeResponse,
    TradeSearchFilter,
)
from app.modules.trades.service import trader_brain
from app.modules.trades.service.upstox_order_client import (
    UpstoxOrderClient,
    limit_price,
    upstox_order_client,
)

_IST = ZoneInfo("Asia/Kolkata")
MAX_PARALLEL_TRADES = 3
CANDLE_CACHE_TTL_SECONDS = 12.0


def _pilot_runner():
    from app.modules.trades.engine.trade_pilot_runner import trade_pilot_runner

    return trade_pilot_runner


def _session_loop_service():
    from app.modules.sessions.service.session_loop_service import session_loop_service

    return session_loop_service


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class TradeService:
    """
    Service managing ActiveTrade lifecycle:
      - Pre-entry risk/capital lot suggestion (`preview_sizing`)
      - Entering a locked pick (`enter_trade`), enforcing max 3 parallel trades per session
      - Direct Upstox order execution when `routeThroughUpstox = True`
      - 1-second live position pilot tick (`tick`) using `trader_brain`
      - Manual SL/Target adjustment (`adjust_levels`) and manual square-off (`manual_exit`)
    """

    def __init__(
        self,
        repo: TradeRepository | None = None,
        order_client: UpstoxOrderClient | None = None,
    ):
        self.repo = repo or trade_repository
        self.orders = order_client or upstox_order_client
        self._locks: dict[int, asyncio.Lock] = {}
        self._candle_cache: dict[int, tuple[float, list[dict[str, Any]]]] = {}

    def _lock_for(self, trade_id: int) -> asyncio.Lock:
        return self._locks.setdefault(trade_id, asyncio.Lock())

    @staticmethod
    def _exchange_for(underlying_code: str) -> str:
        return "MCX" if underlying_code.upper() in {"CRUDEOIL", "NATURALGAS", "GOLD", "GOLDM", "SILVER", "SILVERM"} else "NSE"

    @classmethod
    def _compute_pnl(
        cls, entry_at: float, mark_price: float, quantity: int, lot_units: int, underlying_code: str
    ) -> tuple[float, float, float, float]:
        """Returns `(gross_pnl, charges, net_pnl, pnl_pct)` at `mark_price`."""
        entry_at = float(entry_at)
        mark_price = float(mark_price)
        qty = int(quantity)
        gross = round((mark_price - entry_at) * qty, 2)
        margin_pct = ((mark_price - entry_at) / entry_at * 100.0) if entry_at > 0 else 0.0
        cost_pct = round_trip_cost_pct(entry_at, max(1, int(lot_units)), cls._exchange_for(underlying_code), max(0.0, margin_pct))
        charges = round(entry_at * qty * cost_pct / 100.0, 2)
        net = round(gross - charges, 2)
        capital = entry_at * qty
        pnl_pct = round(net / capital * 100.0, 2) if capital > 0 else 0.0
        return gross, charges, net, pnl_pct

    def to_response(self, t: ActiveTrade, candles_1m: list[dict[str, Any]] | None = None) -> TradeResponse:
        if candles_1m is None:
            cached = self._candle_cache.get(t.id)
            candles_1m = cached[1] if cached else []
        return TradeResponse(
            id=t.id,
            sessionId=t.sessionId,
            pickId=t.pickId,
            opportunityId=t.opportunityId,
            opportunityRef=t.opportunityRef,
            userId=t.userId,
            underlyingCode=t.underlyingCode,
            optionType=t.optionType,
            strike=float(t.strike),
            expiry=t.expiry,
            instrumentKey=t.instrumentKey,
            strategy=t.strategy,
            confidence=int(t.confidence),
            winRatePct=float(t.winRatePct),
            traderProfile=t.traderProfile,
            sessionType=t.sessionType,
            routeThroughUpstox=bool(t.routeThroughUpstox),
            lots=int(t.lots),
            lotUnits=int(t.lotUnits),
            quantity=int(t.quantity),
            plannedEntry=float(t.plannedEntry),
            entryAt=float(t.entryAt),
            capitalUsed=float(t.capitalUsed),
            initialStop=float(t.initialStop),
            initialTarget=float(t.initialTarget),
            currentStop=float(t.currentStop),
            currentTarget=float(t.currentTarget),
            lastPrice=float(t.lastPrice),
            peakPrice=float(t.peakPrice),
            troughPrice=float(t.troughPrice),
            entryOrderId=t.entryOrderId,
            exitOrderId=t.exitOrderId,
            brokerStatus=t.brokerStatus,
            brokerError=t.brokerError,
            tradeState=t.tradeState,
            exitReason=t.exitReason,
            exitPrice=float(t.exitPrice) if t.exitPrice is not None else None,
            grossPnl=float(t.grossPnl),
            charges=float(t.charges),
            netPnl=float(t.netPnl),
            pnlPct=float(t.pnlPct),
            enteredAt=t.enteredAt,
            exitedAt=t.exitedAt,
            holdUntil=t.holdUntil,
            trailEvents=list(t.trailEvents or []),
            marketTelemetry=dict(t.marketTelemetry or {}),
            candles1m=candles_1m,
            status=t.status.name,
            createdAt=t.createdAt,
        )

    async def _session_budget(
        self, db: AsyncSession, session_id: int
    ) -> tuple[Any, list[ActiveTrade], float, float]:
        """Returns `(session_entity, running_trades, available_capital, remaining_loss_budget)`."""
        s = await _session_loop_service().get_session_entity(db, session_id)
        running = await self.repo.running_for_session(db, session_id)
        capital = float(s.capital)
        realized = float(s.realizedPnl or 0.0)
        current_capital = capital + realized
        committed_premium = sum(float(t.capitalUsed) for t in running)
        committed_risk = sum(
            max(0.0, (float(t.entryAt) - float(t.currentStop)) * int(t.quantity)) for t in running
        )
        max_loss = capital * float(s.maxLossPercentage) / 100.0
        loss_used = max(0.0, -realized)
        available_capital = round(max(0.0, current_capital - committed_premium), 2)
        remaining_loss_budget = round(max(0.0, max_loss - loss_used - committed_risk), 2)
        return s, running, available_capital, remaining_loss_budget

    async def preview_sizing(
        self, db: AsyncSession, session_id: int, pick_id: int, entry_at: float | None = None
    ) -> LotSuggestionResponse:
        """
        Computes risk- and capital-based lot sizing for a given `entryAt` price.
        Used by the Enter Trade modal so the trader sees exact suggested lots as they type `entryAt`.
        """
        s, running, available_capital, remaining_loss_budget = await self._session_budget(db, session_id)
        pick = await _session_loop_service().get_pick_entity(db, session_id, pick_id)

        px = round(float(entry_at if entry_at and entry_at > 0 else (pick.lockedPrice or pick.entry)), 2)
        stop = float(pick.stop)
        target = float(pick.target)
        # If entryAt is at or below stop, keep a minimum structural stop distance from the original setup
        if px <= stop:
            orig_stop_pct = max(0.05, (float(pick.entry) - stop) / max(0.05, float(pick.entry)))
            stop = trader_brain.round_tick(max(0.05, px * (1.0 - orig_stop_pct)))
        if target <= px:
            orig_target_pct = max(0.10, (target - float(pick.entry)) / max(0.05, float(pick.entry)))
            target = trader_brain.round_tick(px * (1.0 + orig_target_pct))

        lot_units = max(1, int(pick.lotUnits))
        risk_per_lot = max(0.05, (px - stop) * lot_units)
        premium_per_lot = max(0.05, px * lot_units)

        max_by_risk = int(remaining_loss_budget // risk_per_lot)
        max_by_cash = int(available_capital // premium_per_lot)
        max_affordable = max(0, min(max_by_risk, max_by_cash))

        win_prob = max(0.0, min(1.0, int(pick.confidence) / 100.0))
        # fixed-fractional (research gap 9): size from the stop distance, never from the uncalibrated confidence
        lots_by_trade = int((float(s.capital) * RISK_PER_TRADE_PCT / 100.0) // risk_per_lot)
        one_lot_too_risky = lots_by_trade < 1 and risk_per_lot > float(s.capital) * MAX_ONE_LOT_RISK_PCT / 100.0
        suggested = max(1, min(max_affordable, max(1, lots_by_trade))) if max_affordable >= 1 else 1
        corr = correlated_block(pick.underlyingCode, pick.optionType,
                                [(t.underlyingCode, t.optionType) for t in running])

        qty = suggested * lot_units
        cap_req = round(qty * px, 2)
        risk_amt = round(qty * (px - stop), 2)
        reward_amt = round(qty * (target - px), 2)
        _, charges, net_target, _ = self._compute_pnl(px, target, qty, lot_units, pick.underlyingCode)
        expected_net = round(win_prob * net_target - (1.0 - win_prob) * (risk_amt + charges), 2)

        block_reason: str | None = None
        if s.sessionStatus != "ACTIVE":
            block_reason = f"Session is {s.sessionStatus}"
        elif len(running) >= MAX_PARALLEL_TRADES:
            block_reason = f"Maximum {MAX_PARALLEL_TRADES} parallel active trades already running in this session"
        elif max_by_cash < 1:
            block_reason = "Not enough free capital for 1 lot at this entry price"
        elif max_by_risk < 1:
            block_reason = "Risk per lot exceeds remaining session loss budget"
        elif one_lot_too_risky:
            block_reason = f"1 lot risks more than {MAX_ONE_LOT_RISK_PCT:g}% of session capital"
        elif corr:
            block_reason = corr

        return LotSuggestionResponse(
            sessionId=session_id,
            pickId=pick_id,
            entryAt=px,
            stop=round(stop, 2),
            target=round(target, 2),
            entryMax=round(entry_ceiling(float(pick.entry), float(pick.stop), float(pick.target)), 2),
            lotUnits=lot_units,
            suggestedLots=suggested,
            maxLotsByCash=max_by_cash,
            maxLotsByRisk=max_by_risk,
            maxAffordableLots=max_affordable,
            quantity=qty,
            capitalRequired=cap_req,
            riskAmount=risk_amt,
            rewardAmount=reward_amt,
            expectedNet=expected_net,
            availableCapital=available_capital,
            remainingLossBudget=remaining_loss_budget,
            winProbPct=round(win_prob * 100.0, 1),
            activeTradesCount=len(running),
            maxParallelTrades=MAX_PARALLEL_TRADES,
            canEnter=block_reason is None,
            blockReason=block_reason,
        )

    async def enter_trade(self, db: AsyncSession, request: TradeCreateRequest) -> TradeResponse:
        """
        Enters a locked (or offered) pick, optionally places a live Upstox BUY order when
        `routeThroughUpstox = True`, creates the `ActiveTrade` row, and starts `trade-pilot-{id}`.
        """
        existing = await self.repo.get_by_pick_id(db, request.pickId)
        if existing:
            return self.to_response(existing)

        s, running, available_capital, remaining_loss_budget = await self._session_budget(db, request.sessionId)
        if s.sessionStatus != "ACTIVE":
            raise ConflictException(message=f"Session is {s.sessionStatus}", error={"code": "SESSION_NOT_ACTIVE"})
        now = datetime.now(UTC)
        if s.closeAt is not None and now >= _utc(s.closeAt):
            raise ConflictException(message="Session trading hours are over", error={"code": "SESSION_HOURS_OVER"})
        if len(running) >= MAX_PARALLEL_TRADES:
            raise ConflictException(
                message=f"Session already has {MAX_PARALLEL_TRADES} parallel active trades running",
                error={"code": "MAX_PARALLEL_TRADES", "maxParallelTrades": MAX_PARALLEL_TRADES},
            )

        pick = await _session_loop_service().get_pick_entity(db, request.sessionId, request.pickId)
        corr = correlated_block(pick.underlyingCode, pick.optionType,
                                [(t.underlyingCode, t.optionType) for t in running])
        if corr:
            raise ConflictException(message=corr, error={"code": "CORRELATED_EXPOSURE"})
        if pick.pickState == "OFFERED":
            pick.pickState = "LOCKED"
            pick.lockedAt = now
            if pick.lockedPrice is None:
                pick.lockedPrice = await opportunity_run_service.live_premium(db, pick.instrumentKey)

        suggestion = await self.preview_sizing(db, request.sessionId, request.pickId, request.entryAt)
        entry_at = round(float(request.entryAt if request.entryAt else suggestion.entryAt), 2)
        lots = int(request.lots if request.lots else suggestion.suggestedLots)
        if lots < 1:
            raise BadRequestException(message="Lots must be at least 1")

        initial_stop = round(float(request.initialStop if request.initialStop else suggestion.stop), 2)
        initial_target = round(float(request.initialTarget if request.initialTarget else suggestion.target), 2)
        if initial_stop >= entry_at:
            raise BadRequestException(message=f"Stop loss (₹{initial_stop}) must be below entry price (₹{entry_at})")
        if initial_target <= entry_at:
            raise BadRequestException(message=f"Target (₹{initial_target}) must be above entry price (₹{entry_at})")

        lot_units = max(1, int(pick.lotUnits))
        quantity = lots * lot_units
        capital_used = round(quantity * entry_at, 2)
        risk_amount = round(quantity * (entry_at - initial_stop), 2)

        if capital_used > available_capital + 0.01:
            raise ConflictException(
                message=f"Capital required (₹{capital_used:,.2f}) exceeds available session capital (₹{available_capital:,.2f})",
                error={"code": "INSUFFICIENT_CAPITAL"},
            )
        if risk_amount > remaining_loss_budget + 0.01:
            raise ConflictException(
                message=f"Trade risk (₹{risk_amount:,.2f}) exceeds remaining session loss budget (₹{remaining_loss_budget:,.2f})",
                error={"code": "LOSS_BUDGET"},
            )

        win_rate_pct = await opportunity_run_service.resolve_win_rate_pct(
            db, pick.underlyingCode, pick.strategy, int(pick.confidence)
        )
        profile = trader_brain.select_profile(win_rate_pct, int(pick.confidence))

        entry_order_id: str | None = None
        broker_status = "SIMULATED"
        broker_error: str | None = None
        execution: dict[str, Any] = {"plannedEntry": float(pick.entry), "requestedEntry": entry_at,
                                     "orderType": "SIMULATED"}
        if s.routeThroughUpstox:
            # Marketable LIMIT, not MARKET: caps the chase at ENTRY_LIMIT_BUFFER_TICKS (research gap 5).
            px = limit_price(entry_at, "BUY", settings.ENTRY_LIMIT_BUFFER_TICKS)
            order_res = await self.orders.place_order(
                db,
                user_id=s.userId,
                instrument_key=pick.instrumentKey,
                quantity=quantity,
                transaction_type="BUY",
                order_type="LIMIT",
                price=px,
                tag=f"ENTRY-S{s.id}-P{pick.id}",
            )
            entry_order_id = order_res["orderId"]
            broker_status = order_res["status"]
            broker_error = order_res["error"]
            if not order_res["ok"]:
                raise ConflictException(message=f"Upstox rejected the entry order: {order_res['error']}",
                                        error={"code": "BROKER_REJECTED"})
            fill = await self.orders.wait_for_fill(db, s.userId, entry_order_id, settings.ENTRY_FILL_TIMEOUT_S)
            filled = fill.get("filledQty")
            complete = (fill.get("status") or "").lower() == "complete"
            if not complete:
                # no chasing: whatever did not fill in ENTRY_FILL_TIMEOUT_S is cancelled
                await self.orders.cancel_order(db, s.userId, entry_order_id)
                filled_qty = int(filled or 0) - int(filled or 0) % lot_units
                if filled_qty <= 0:
                    raise ConflictException(
                        message=(f"Entry LIMIT ₹{px:.2f} not filled within {settings.ENTRY_FILL_TIMEOUT_S:g}s: "
                                 "order cancelled, nothing bought (price moved away -- do not chase)"),
                        error={"code": "ENTRY_NOT_FILLED", "orderId": entry_order_id},
                    )
                quantity, lots = filled_qty, filled_qty // lot_units  # partial fill: keep only what was bought
                capital_used = round(quantity * entry_at, 2)
            avg = fill.get("averagePrice")
            execution.update({"orderType": "LIMIT", "limitPrice": px, "sentAt": order_res.get("sentAt"),
                              "latencyMs": order_res.get("latencyMs"), "fillStatus": fill.get("status"),
                              "fillPrice": avg, "filledQty": quantity})
            if avg:
                # implementation shortfall vs the price the engine planned on (positive = paid more)
                execution["slippagePct"] = round((avg - float(pick.entry)) / float(pick.entry) * 100, 3)
                entry_at = round(float(avg), 2)

        gross, charges, net, pnl_pct = self._compute_pnl(
            entry_at, entry_at, quantity, lot_units, pick.underlyingCode
        )
        initial_event = {
            "at": now.isoformat(),
            "action": "ENTERED",
            "oldStop": initial_stop,
            "newStop": initial_stop,
            "oldTarget": initial_target,
            "newTarget": initial_target,
            "ltp": entry_at,
            "reason": (
                f"Entered {lots} lot(s) ({quantity} qty) at ₹{entry_at:.2f} · Profile: {profile} "
                f"(winRate {win_rate_pct:.0f}%) · Initial SL ₹{initial_stop:.2f}, Target ₹{initial_target:.2f}"
                + (f" · Upstox order {entry_order_id or broker_status}" if s.routeThroughUpstox else " · Simulated")
            ),
        }

        entity = ActiveTrade(
            sessionId=s.id,
            pickId=pick.id,
            opportunityId=pick.opportunityId,
            opportunityRef=pick.opportunityRef,
            userId=s.userId,
            underlyingCode=pick.underlyingCode,
            optionType=pick.optionType,
            strike=float(pick.strike),
            expiry=pick.expiry,
            instrumentKey=pick.instrumentKey,
            strategy=pick.strategy,
            confidence=int(pick.confidence),
            winRatePct=win_rate_pct,
            traderProfile=profile,
            sessionType=s.sessionType,
            routeThroughUpstox=bool(s.routeThroughUpstox),
            lots=lots,
            lotUnits=lot_units,
            quantity=quantity,
            plannedEntry=float(pick.entry),
            entryAt=entry_at,
            capitalUsed=capital_used,
            initialStop=initial_stop,
            initialTarget=initial_target,
            currentStop=initial_stop,
            currentTarget=initial_target,
            lastPrice=entry_at,
            peakPrice=entry_at,
            troughPrice=entry_at,
            entryOrderId=entry_order_id,
            exitOrderId=None,
            brokerStatus=broker_status,
            brokerError=broker_error,
            tradeState="RUNNING",
            exitReason=None,
            exitPrice=None,
            grossPnl=gross,
            charges=charges,
            netPnl=net,
            pnlPct=pnl_pct,
            enteredAt=now,
            exitedAt=None,
            holdUntil=_utc(pick.holdUntil),
            trailEvents=[initial_event],
            marketTelemetry={
                "volumeRatio": 1.0,
                "candleStructure": "NEUTRAL",
                "momentumState": "STEADY",
                "progressPct": 0.0,
                "liveProgressPct": 0.0,
                "rrNow": round((initial_target - entry_at) / max(0.05, entry_at - initial_stop), 2),
                "inRunnerMode": False,
                "execution": execution,
            },
        )
        saved = await self.repo.save(db, entity)
        await db.commit()
        _pilot_runner().start(saved.id)
        return self.to_response(saved)

    async def open_exposure(self, db: AsyncSession, session_id: int) -> list[tuple[str, str]]:
        """(underlyingCode, optionType) of this session's RUNNING trades -- for the correlated-exposure cap."""
        return [(t.underlyingCode, t.optionType) for t in await self.repo.running_for_session(db, session_id)]

    async def week_net_pnl(self, db: AsyncSession, user_id: int, now: datetime | None = None) -> float:
        """Realised net P&L of this user's trades since Monday 00:00 IST of the current week."""
        now_ist = (now or datetime.now(UTC)).astimezone(_IST)
        monday = (now_ist - timedelta(days=now_ist.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.repo.net_pnl_exited_since(db, user_id, monday.astimezone(UTC))

    async def get_by_id(self, db: AsyncSession, trade_id: int) -> TradeResponse:
        entity = await self.repo.get_by_id(db, trade_id)
        if not entity:
            raise NotFoundException(message=f"Trade {trade_id} not found")
        candles = await self._candles_for(db, entity)
        return self.to_response(entity, candles_1m=candles)

    async def search(self, db: AsyncSession, filter_obj: TradeSearchFilter) -> PageResult[TradeResponse]:
        page = await self.repo.search(db, filter_obj)
        return PageResult(
            list=[self.to_response(e) for e in page.list],
            page=page.page,
            limit=page.limit,
            totalPages=page.totalPages,
            totalItems=page.totalItems,
        )

    async def _candles_for(self, db: AsyncSession, t: ActiveTrade, force: bool = False) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        cached = self._candle_cache.get(t.id)
        if not force and cached and (now_mono - cached[0]) < CANDLE_CACHE_TTL_SECONDS:
            return cached[1]
        trade_date = _utc(t.enteredAt).astimezone(_IST).strftime("%Y-%m-%d")
        bars = await opportunity_run_service.option_candles_1m(db, t.instrumentKey, trade_date=trade_date)
        self._candle_cache[t.id] = (now_mono, bars)
        return bars

    async def _exit_quantity(self, db: AsyncSession, t: ActiveTrade) -> int:
        """Quantity the broker exit may SELL. Never more than the entry actually bought: an intraday SELL with no
        long position would open a NAKED SHORT option. Unfilled / rejected entries -> 0 (no exit order at all)."""
        if not t.entryOrderId or t.brokerStatus in ("REJECTED", "ERROR"):
            return 0
        qty = int(t.quantity)
        fill = await self.orders.fetch_fill(db, t.userId, t.entryOrderId)
        if fill.get("filledQty") is not None:
            qty = min(qty, int(fill["filledQty"] or 0))
        return qty

    async def _finalize_exit(
        self,
        db: AsyncSession,
        t: ActiveTrade,
        exit_price: float,
        exit_reason: str,
        reason_text: str,
        now: datetime,
    ) -> None:
        exit_price = round(float(exit_price), 2)
        gross, charges, net, pnl_pct = self._compute_pnl(
            float(t.entryAt), exit_price, int(t.quantity), int(t.lotUnits), t.underlyingCode
        )
        if t.routeThroughUpstox:
            sell_qty = await self._exit_quantity(db, t)
            if sell_qty <= 0:
                t.brokerError = "Entry not filled at the broker: no exit order sent (cancel any open entry order)"
            else:
                order_res = await self.orders.place_order(
                    db,
                    user_id=t.userId,
                    instrument_key=t.instrumentKey,
                    quantity=sell_qty,
                    transaction_type="SELL",
                    order_type="MARKET",  # carries market_protection (see UpstoxOrderClient)
                    price=exit_price,
                    tag=f"EXIT-T{t.id}",
                )
                t.exitOrderId = order_res["orderId"]
                t.brokerStatus = order_res["status"]
                if order_res["error"]:
                    t.brokerError = order_res["error"]

        t.tradeState = "EXITED"
        t.exitReason = exit_reason
        t.exitPrice = exit_price
        t.lastPrice = exit_price
        t.peakPrice = max(float(t.peakPrice), exit_price)
        t.troughPrice = min(float(t.troughPrice), exit_price)
        t.grossPnl = gross
        t.charges = charges
        t.netPnl = net
        t.pnlPct = pnl_pct
        t.exitedAt = now

        events = list(t.trailEvents or [])
        events.append(
            {
                "at": now.isoformat(),
                "action": f"EXIT:{exit_reason}",
                "oldStop": float(t.currentStop),
                "newStop": float(t.currentStop),
                "oldTarget": float(t.currentTarget),
                "newTarget": float(t.currentTarget),
                "ltp": exit_price,
                "reason": (
                    f"{reason_text} · Net P&L: ₹{net:,.2f} ({pnl_pct:+.2f}%)"
                    + (f" · Upstox SELL order {t.exitOrderId or t.brokerStatus}" if t.routeThroughUpstox else "")
                ),
            }
        )
        t.trailEvents = events
        await _session_loop_service().record_trade_realized_pnl(db, t.sessionId, net)

    async def tick(self, db: AsyncSession, trade_id: int) -> TradeLiveSnapshot:
        """One 1-second tick of the trade's dedicated pilot loop."""
        async with self._lock_for(trade_id):
            t = await self.repo.get_by_id(db, trade_id)
            if not t:
                raise NotFoundException(message=f"Trade {trade_id} not found")
            now = datetime.now(UTC)
            candles = await self._candles_for(db, t)
            if t.tradeState != "RUNNING":
                return TradeLiveSnapshot(tradeId=t.id, serverTime=now, trade=self.to_response(t, candles_1m=candles))

            s = await _session_loop_service().get_session_entity(db, t.sessionId)
            live_px = await opportunity_run_service.live_premium(db, t.instrumentKey)
            ltp = float(live_px) if live_px is not None and live_px > 0 else float(t.lastPrice)

            t.lastPrice = ltp
            t.peakPrice = max(float(t.peakPrice), ltp)
            t.troughPrice = min(float(t.troughPrice), ltp)

            gross, charges, net, pnl_pct = self._compute_pnl(
                float(t.entryAt), ltp, int(t.quantity), int(t.lotUnits), t.underlyingCode
            )
            t.grossPnl = gross
            t.charges = charges
            t.netPnl = net
            t.pnlPct = pnl_pct

            decision = trader_brain.evaluate_tick(
                entry_at=float(t.entryAt),
                initial_stop=float(t.initialStop),
                initial_target=float(t.initialTarget),
                current_stop=float(t.currentStop),
                current_target=float(t.currentTarget),
                peak_price=float(t.peakPrice),
                ltp=ltp,
                trader_profile=t.traderProfile,
                candles_1m=candles,
                now=now,
                close_at=_utc(s.closeAt) if s.closeAt else None,
                momentum_trail=MOMO_EXIT if SETUP_POLICY.get(t.strategy or "") in ("CORE", "MERGED") else None,
            )
            # keep the entry's execution record (fill, slippage) across ticks
            t.marketTelemetry = {**decision.telemetry, "execution": (t.marketTelemetry or {}).get("execution")}

            if decision.action == "EXIT":
                await self._finalize_exit(
                    db,
                    t,
                    exit_price=decision.exitPrice or ltp,
                    exit_reason=decision.exitReason or "TARGET_HIT",
                    reason_text=decision.reason,
                    now=now,
                )
            elif decision.action in ("TRAIL_SL", "TRAIL_TARGET", "TRAIL_BOTH"):
                old_stop = float(t.currentStop)
                old_target = float(t.currentTarget)
                t.currentStop = decision.newStop
                t.currentTarget = decision.newTarget
                events = list(t.trailEvents or [])
                events.append(
                    {
                        "at": now.isoformat(),
                        "action": decision.action,
                        "oldStop": old_stop,
                        "newStop": decision.newStop,
                        "oldTarget": old_target,
                        "newTarget": decision.newTarget,
                        "ltp": ltp,
                        "reason": decision.reason,
                    }
                )
                t.trailEvents = events

            await db.flush()
            return TradeLiveSnapshot(tradeId=t.id, serverTime=now, trade=self.to_response(t, candles_1m=candles))

    async def adjust_levels(self, db: AsyncSession, trade_id: int, request: TradeAdjustRequest) -> TradeResponse:
        """Manual adjustment of currentStop and/or currentTarget by the user."""
        async with self._lock_for(trade_id):
            t = await self.repo.get_by_id(db, trade_id)
            if not t:
                raise NotFoundException(message=f"Trade {trade_id} not found")
            if t.tradeState != "RUNNING":
                raise ConflictException(message=f"Trade is already {t.tradeState}", error={"code": "TRADE_NOT_RUNNING"})

            old_stop = float(t.currentStop)
            old_target = float(t.currentTarget)
            new_stop = round(float(request.currentStop), 2) if request.currentStop is not None else old_stop
            new_target = round(float(request.currentTarget), 2) if request.currentTarget is not None else old_target
            if new_stop >= new_target:
                raise BadRequestException(message="Stop-loss must be below Target")

            t.currentStop = new_stop
            t.currentTarget = new_target
            now = datetime.now(UTC)
            events = list(t.trailEvents or [])
            events.append(
                {
                    "at": now.isoformat(),
                    "action": "MANUAL_ADJUST",
                    "oldStop": old_stop,
                    "newStop": new_stop,
                    "oldTarget": old_target,
                    "newTarget": new_target,
                    "ltp": float(t.lastPrice),
                    "reason": request.reason or f"Manual override: SL ₹{new_stop:.2f}, Target ₹{new_target:.2f}",
                }
            )
            t.trailEvents = events
            await db.commit()
            candles = await self._candles_for(db, t)
            snap = TradeLiveSnapshot(tradeId=t.id, serverTime=now, trade=self.to_response(t, candles_1m=candles))
            _pilot_runner().publish_snapshot(t.id, snap)
            return snap.trade

    async def manual_exit(self, db: AsyncSession, trade_id: int, request: TradeExitRequest) -> TradeResponse:
        """Manual square-off triggered by the user."""
        async with self._lock_for(trade_id):
            t = await self.repo.get_by_id(db, trade_id)
            if not t:
                raise NotFoundException(message=f"Trade {trade_id} not found")
            if t.tradeState != "RUNNING":
                return self.to_response(t)

            now = datetime.now(UTC)
            live_px = request.exitPrice or await opportunity_run_service.live_premium(db, t.instrumentKey)
            exit_px = float(live_px) if live_px is not None and live_px > 0 else float(t.lastPrice)
            exit_reason = (request.reason or "MANUAL_EXIT").upper()
            await self._finalize_exit(
                db,
                t,
                exit_price=exit_px,
                exit_reason=exit_reason,
                reason_text=f"Manual exit at ₹{exit_px:.2f}",
                now=now,
            )
            await db.commit()
            candles = await self._candles_for(db, t)
            snap = TradeLiveSnapshot(tradeId=t.id, serverTime=now, trade=self.to_response(t, candles_1m=candles))
            _pilot_runner().publish_snapshot(t.id, snap)
            _pilot_runner().stop(t.id)
            return snap.trade


trade_service = TradeService()

