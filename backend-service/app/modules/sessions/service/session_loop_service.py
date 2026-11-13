import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.modules.opportunities.service import positioning

from app.core.exception.app_exceptions import ConflictException, NotFoundException
from app.core.pagination.page_result import PageResult
from app.modules.opportunities.service.run_service import opportunity_run_service
from app.modules.sessions.entity.session_pick_entity import SessionPick
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.repository.session_pick_repository import SessionPickRepository
from app.modules.sessions.repository.trading_session_repository import TradingSessionRepository
from app.modules.sessions.schema.session_pick_schema import (
    SessionCapitalResponse,
    SessionLoopResponse,
    SessionPickResponse,
    SessionPickSearchFilter,
)
from app.modules.sessions.service.session_sizing import (
    MAX_OPEN_OFFERS,
    MAX_OPPORTUNITY_AGE_SECONDS,
    MIN_PICK_WINDOW_SECONDS,
    CapitalState,
    capital_state,
    correlated_block,
    size_multiplier,
    lots_for,
    rank_key,
    size_candidate,
)
from app.modules.trades.service.trader_presets import (
    ALL_PRESET_TRADER_CODES,
    assign_trader_for_opportunity,
    get_trader_preset,
)

_IST = ZoneInfo("Asia/Kolkata")
WEEKLY_MAX_LOSS_PCT = 4.0  # research gap 9: stop for the week once realised losses reach 4% of session capital
MAX_PARALLEL_TRADES = 3


class OpportunityReader(Protocol):
    async def saved_candidates(
        self, session: AsyncSession, codes: list[str], max_age_seconds: int
    ) -> list[dict[str, Any]]: ...

    async def live_premium(self, session: AsyncSession, instrument_key: str | None) -> float | None: ...


@dataclass(frozen=True)
class _CommitmentItem:
    capitalRequired: float
    riskAmount: float


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _trade_service():
    from app.modules.trades.service.trade_service import trade_service

    return trade_service


class SessionLoopService:
    """
    The session loop (supports MANUAL, SEMI_AUTO, and FULL_AUTO):
      - MANUAL: sizes and offers top ranked opportunities; trader locks & enters manually.
      - SEMI_AUTO: sizes opportunities and automatically locks the #1 best opportunity when < 3 active slots.
      - FULL_AUTO: sizes opportunities, automatically locks the #1 best opportunity, and immediately enters
        the trade into its dedicated Trader loop (`trade-pilot-{tradeId}`) up to 3 parallel active trades.
    """

    def __init__(
        self,
        session_repo: TradingSessionRepository | None = None,
        pick_repo: SessionPickRepository | None = None,
        opportunities: OpportunityReader | None = None,
    ):
        self.sessions = session_repo or TradingSessionRepository()
        self.picks = pick_repo or SessionPickRepository()
        self.opportunities = opportunities or opportunity_run_service
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, session_id: int) -> asyncio.Lock:
        return self._locks.setdefault(session_id, asyncio.Lock())

    # ───────────────────────── cross-module public helpers ─────────────────────────
    async def get_session_entity(self, db: AsyncSession, session_id: int) -> TradingSession:
        return await self._load(db, session_id)

    async def get_pick_entity(self, db: AsyncSession, session_id: int, pick_id: int) -> SessionPick:
        pick = await self.picks.get_by_id(db, pick_id)
        if not pick or pick.sessionId != session_id:
            raise NotFoundException(message=f"Pick {pick_id} not found in session {session_id}")
        return pick

    async def record_trade_realized_pnl(self, db: AsyncSession, session_id: int, net_pnl: float) -> None:
        s = await self.sessions.get_by_id(db, session_id)
        if s is not None:
            s.realizedPnl = round(float(s.realizedPnl or 0.0) + float(net_pnl), 2)
            await db.flush()

    # ───────────────────────── mapping ─────────────────────────
    @staticmethod
    def pick_response(p: SessionPick, now: datetime, trade_id: int | None = None) -> SessionPickResponse:
        entry, stop, target = float(p.entry), float(p.stop), float(p.target)
        left = (_utc(p.expiresAt) - now).total_seconds() if p.pickState == "OFFERED" else 0.0
        state = "EXPIRED" if p.pickState == "OFFERED" and left <= 0 else p.pickState
        t_code = assign_trader_for_opportunity(p.strategy, int(p.confidence), float(p.rewardRisk))
        t_preset = get_trader_preset(t_code)
        return SessionPickResponse(
            id=p.id, sessionId=p.sessionId, opportunityId=p.opportunityId, opportunityRef=p.opportunityRef,
            underlyingCode=p.underlyingCode, optionType=p.optionType, strike=float(p.strike), expiry=p.expiry,
            instrumentKey=p.instrumentKey, strategy=p.strategy, traderCode=t_code, traderName=t_preset["name"],
            confidence=p.confidence,
            entry=entry, entryMax=float(p.entryMax), stop=stop, target=target,
            stopPct=round((entry - stop) / entry * 100, 2), targetPct=round((target - entry) / entry * 100, 2),
            rewardRisk=float(p.rewardRisk), lots=p.lots, lotUnits=p.lotUnits, quantity=p.quantity,
            capitalRequired=float(p.capitalRequired), riskAmount=float(p.riskAmount),
            rewardAmount=float(p.rewardAmount), expectedNet=float(p.expectedNet),
            capitalAtPick=float(p.capitalAtPick), availableAtPick=float(p.availableAtPick),
            reasons=p.reasons or [], risks=p.risks or [], pickState=state,
            signalAt=p.signalAt, holdUntil=p.holdUntil, offeredAt=p.offeredAt, expiresAt=p.expiresAt,
            lockedAt=p.lockedAt, lockedPrice=float(p.lockedPrice) if p.lockedPrice is not None else None,
            tradeId=trade_id,
            winProbPct=float(p.confidence), usagePct=round(float(p.capitalRequired) / float(p.availableAtPick) * 100, 1)
            if float(p.availableAtPick) > 0 else 0.0, secondsLeft=round(max(0.0, left), 2), createdAt=p.createdAt,
        )

    @staticmethod
    def _ranked(picks: list[SessionPick]) -> list[SessionPick]:
        """Best first: expected net rupees, then confidence, then reward:risk."""
        return sorted(picks, key=lambda p: (float(p.expectedNet), p.confidence, float(p.rewardRisk)), reverse=True)

    @staticmethod
    def _refit(p: SessionPick, lots: int, cap: CapitalState) -> None:
        """Re-size an open offer to the capital that is free NOW (another row may have been locked)."""
        old = max(1, p.lots)
        p.expectedNet = round(float(p.expectedNet) / old * lots, 2)
        p.lots, p.quantity = lots, lots * p.lotUnits
        p.capitalRequired = round(p.quantity * float(p.entry), 2)
        p.riskAmount = round(p.quantity * (float(p.entry) - float(p.stop)), 2)
        p.rewardAmount = round(p.quantity * (float(p.target) - float(p.entry)), 2)
        p.capitalAtPick, p.availableAtPick = cap.currentCapital, cap.availableCapital

    @staticmethod
    def _codes(s: TradingSession) -> list[str]:
        return list(s.underlyings if s.scope == "INDEX" else s.commodityItems) or []

    async def _session_commitments(
        self, db: AsyncSession, s: TradingSession, locked_picks: list[SessionPick]
    ) -> tuple[CapitalState, list[int], dict[int, int], list[SessionPick]]:
        """
        Computes `CapitalState` from active `RUNNING` trades + any un-entered `LOCKED` picks.
        Once a `LOCKED` pick is entered into `ActiveTrade`, its commitment is tracked by that `ActiveTrade`
        while `RUNNING`, and freed once `EXITED` (with its net P&L added to `s.realizedPnl`).
        """
        try:
            all_trades = await _trade_service().repo.all_for_session(db, s.id)
        except Exception:
            all_trades = []

        running_trades = [t for t in all_trades if t.tradeState == "RUNNING"]
        entered_pick_ids = {int(t.pickId) for t in all_trades}
        pick_to_trade = {int(t.pickId): int(t.id) for t in all_trades}

        pending_locked = [p for p in locked_picks if p.id not in entered_pick_ids]
        commitments: list[Any] = [
            _CommitmentItem(
                capitalRequired=float(t.capitalUsed),
                riskAmount=max(0.0, (float(t.entryAt) - float(t.currentStop)) * int(t.quantity)),
            )
            for t in running_trades
        ]
        # Only include pending locked picks if no active trades exist in tests or when awaiting SEMI_AUTO entry
        commitments.extend(pending_locked)

        cap = capital_state(s.capital, s.maxLossPercentage, s.realizedPnl, commitments)
        return cap, [int(t.id) for t in running_trades], pick_to_trade, pending_locked

    def _loop_response(
        self,
        s: TradingSession,
        now: datetime,
        cap: CapitalState,
        state: str,
        message: str,
        picks: list[SessionPick] | None = None,
        locked_picks: list[SessionPick] | None = None,
        active_trade_ids: list[int] | None = None,
        pick_to_trade: dict[int, int] | None = None,
        candidates: int = 0,
        excluded: dict[str, int] | None = None,
    ) -> SessionLoopResponse:
        pt = pick_to_trade or {}
        active_ids = active_trade_ids or []
        return SessionLoopResponse(
            sessionId=s.id,
            serverTime=now,
            state=state,
            message=message,
            picks=[self.pick_response(p, now, trade_id=pt.get(p.id)) for p in self._ranked(picks or [])],
            lockedPicks=[self.pick_response(p, now, trade_id=pt.get(p.id)) for p in (locked_picks or [])],
            capital=SessionCapitalResponse(
                **cap.as_dict(),
                activeTradesCount=len(active_ids),
                maxParallelTrades=MAX_PARALLEL_TRADES,
                activeTradeIds=active_ids,
            ),
            scanned={"candidates": candidates, "excluded": excluded or {}},
        )

    async def _load(self, db: AsyncSession, session_id: int) -> TradingSession:
        s = await self.sessions.get_by_id(db, session_id)
        if not s:
            raise NotFoundException(message=f"Trading session {session_id} not found")
        return s

    # ───────────────────────── loop tick ─────────────────────────
    async def tick(self, db: AsyncSession, session_id: int) -> SessionLoopResponse:
        async with self._lock_for(session_id):
            s = await self._load(db, session_id)
            now = datetime.now(UTC)
            open_picks = await self.picks.open_picks(db, session_id)
            for p in open_picks:
                if p.pickState == "OFFERED" and _utc(p.expiresAt) <= now:
                    p.pickState = "EXPIRED"
            await db.flush()
            locked = [p for p in open_picks if p.pickState == "LOCKED"]
            cap, active_ids, pick_to_trade, pending_locked = await self._session_commitments(db, s, locked)

            if s.sessionStatus != "ACTIVE":
                return self._loop_response(
                    s, now, cap, "SESSION_CLOSED", f"Session is {s.sessionStatus}",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )
            today = now.astimezone(_IST).date().isoformat()
            if s.tradeDate != today:
                return self._loop_response(
                    s, now, cap, "SESSION_CLOSED", f"Session trade date {s.tradeDate} is not today ({today})",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )
            if s.closeAt is not None and now >= _utc(s.closeAt):
                for p in open_picks:
                    if p.pickState == "OFFERED":
                        p.pickState = "EXPIRED"
                s.sessionStatus, s.closedAt = "CLOSED", now
                await db.flush()
                at_ = _utc(s.closeAt).astimezone(_IST).strftime("%H:%M")
                return self._loop_response(
                    s, now, cap, "SESSION_CLOSED", f"Session closed at {at_} IST",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )
            if s.sessionType not in ("MANUAL", "SEMI_AUTO", "FULL_AUTO"):
                return self._loop_response(
                    s, now, cap, "UNSUPPORTED_TYPE",
                    f"{s.sessionType} sessions are not supported",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )
            if s.startAt is not None and now < _utc(s.startAt):
                at_ = _utc(s.startAt).astimezone(_IST).strftime("%H:%M")
                return self._loop_response(
                    s, now, cap, "SCHEDULED", f"Starts at {at_} IST",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )
            if cap.lossUsed >= cap.maxLossAmount:
                if s.haltedAt is None:
                    s.haltReason, s.haltedAt = "MAX_LOSS", now
                    await db.flush()
                return self._loop_response(
                    s, now, cap, "HALTED", f"Session loss limit reached ({s.maxLossPercentage}% of capital)",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )

            try:
                week_net = await _trade_service().week_net_pnl(db, s.userId, now)
            except Exception:
                week_net = 0.0
            if week_net <= -float(s.capital) * WEEKLY_MAX_LOSS_PCT / 100.0:
                if s.haltedAt is None:
                    s.haltReason, s.haltedAt = "WEEKLY_LOSS", now
                    await db.flush()
                return self._loop_response(
                    s, now, cap, "HALTED",
                    f"Weekly loss limit reached (Rs {week_net:,.0f}, max {WEEKLY_MAX_LOSS_PCT:g}% of capital): "
                    "review before trading again",
                    locked_picks=pending_locked, active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                )

            try:
                exposure = await _trade_service().open_exposure(db, s.id)
            except Exception:
                exposure = []
            exposure += [(p.underlyingCode, p.optionType) for p in pending_locked]

            # Open offers stay on the table until their opportunity expires, re-fitted to the capital free right now
            # (and dropped once a lock elsewhere makes them a second same-direction bet on the correlated index book)
            live = [p for p in open_picks if p.pickState == "OFFERED"]
            for p in list(live):
                lots, _ = lots_for(float(p.entry), float(p.stop), p.lotUnits, p.confidence, cap)
                if lots is None or correlated_block(p.underlyingCode, p.optionType, exposure):
                    p.pickState = "EXPIRED"
                    live.remove(p)
                elif lots != p.lots:
                    self._refit(p, lots, cap)
            await db.flush()

            room = MAX_OPEN_OFFERS - len(live)
            candidates = await self.opportunities.saved_candidates(db, self._codes(s), MAX_OPPORTUNITY_AGE_SECONDS)
            seen = await self.picks.offered_opportunity_ids(db, session_id)
            excluded: dict[str, int] = {}

            def drop(reason: str) -> None:
                excluded[reason] = excluded.get(reason, 0) + 1

            overlay_on = settings.POSITIONING_OVERLAY_ENABLED
            pos_bias = 0
            if overlay_on:
                try:
                    pos_bias = int((positioning.snapshot() or {}).get("bias") or 0)
                except Exception:  # noqa: BLE001 -- no participant file yet: neutral
                    pos_bias = 0

            active_traders = set(getattr(s, "traders", None) or ALL_PRESET_TRADER_CODES)
            ranked: list[tuple[tuple, dict[str, Any], Any]] = []
            for opp in candidates:
                opp_trader = assign_trader_for_opportunity(
                    opp.get("strategy"), int(opp.get("confidence") or 70), float(opp.get("rewardRisk") or 1.5)
                )
                if active_traders and opp_trader not in active_traders:
                    drop("trader not active in session")
                    continue
                opp["sizeMult"] = size_multiplier(opp.get("strategy"), opp["optionType"], pos_bias, overlay_on)
                if int(opp["id"]) in seen:
                    drop("already offered")
                    continue
                if (_utc(datetime.fromisoformat(opp["validUntil"])) - now).total_seconds() < MIN_PICK_WINDOW_SECONDS:
                    drop("expires too soon")
                    continue
                corr = correlated_block(opp["underlyingCode"], opp["optionType"], exposure)
                if corr:
                    drop(corr)
                    continue
                sized, why = size_candidate(opp, cap)
                if sized is None:
                    drop(why or "excluded")
                    continue
                ranked.append((rank_key(opp, sized), opp, sized))

            ranked.sort(key=lambda x: x[0], reverse=True)
            for _, opp, z in ranked[: max(0, room)]:
                valid_until = _utc(datetime.fromisoformat(opp["validUntil"]))
                pick = SessionPick(
                    sessionId=s.id, opportunityId=int(opp["id"]), opportunityRef=opp["ref"],
                    underlyingCode=opp["underlyingCode"], optionType=opp["optionType"], strike=opp["strike"],
                    expiry=opp["expiry"], instrumentKey=opp.get("instrumentKey"), strategy=opp.get("strategy"),
                    confidence=int(opp["confidence"]), entry=opp["entry"], entryMax=z.entryMax, stop=opp["stop"],
                    target=opp["target"], rewardRisk=opp["rewardRisk"], lots=z.lots, lotUnits=z.lotUnits,
                    quantity=z.quantity, capitalRequired=z.capitalRequired, riskAmount=z.riskAmount,
                    rewardAmount=z.rewardAmount, expectedNet=z.expectedNet, capitalAtPick=cap.currentCapital,
                    availableAtPick=cap.availableCapital, reasons=list(opp.get("reasons") or []),
                    risks=list(opp.get("risks") or []), pickState="OFFERED",
                    signalAt=_utc(datetime.fromisoformat(opp["createdAt"])), holdUntil=valid_until,
                    offeredAt=now, expiresAt=valid_until,
                )
                await self.picks.save(db, pick)
                live.append(pick)
            if len(ranked) > room:
                excluded["table full"] = len(ranked) - max(0, room)

            # ─── SEMI_AUTO & FULL_AUTO Automation ───
            # Both SEMI_AUTO and FULL_AUTO automatically select the #1 ranked opportunity, size it against
            # session capital/risk, lock the pick, and enter the ActiveTrade loop (navigation to /trades/$tradeId).
            # SEMI_AUTO marks exit signals on the live Trader graph for user exit; FULL_AUTO also auto-exits.
            if s.sessionType in ("SEMI_AUTO", "FULL_AUTO") and live:
                if len(active_ids) < MAX_PARALLEL_TRADES:
                    best_pick = self._ranked(live)[0]
                    live_px = await self.opportunities.live_premium(db, best_pick.instrumentKey)
                    fill_px = float(live_px) if live_px is not None and live_px > 0 else float(best_pick.entry)
                    if fill_px <= float(best_pick.entryMax) + 1e-6:
                        best_pick.pickState = "LOCKED"
                        best_pick.lockedAt = now
                        best_pick.lockedPrice = fill_px
                        live.remove(best_pick)
                        await db.flush()
                        from app.modules.trades.schema.trade_schema import TradeCreateRequest

                        try:
                            entered = await _trade_service().enter_trade(
                                db,
                                TradeCreateRequest(
                                    sessionId=s.id,
                                    pickId=best_pick.id,
                                    entryAt=fill_px,
                                    lots=int(best_pick.lots),
                                ),
                            )
                            active_ids.append(entered.id)
                            pick_to_trade[best_pick.id] = entered.id
                        except Exception:
                            pending_locked.append(best_pick)
                        locked = [p for p in await self.picks.open_picks(db, session_id) if p.pickState == "LOCKED"]
                        cap, active_ids, pick_to_trade, pending_locked = await self._session_commitments(db, s, locked)

            if not live:
                if len(active_ids) >= MAX_PARALLEL_TRADES:
                    msg = f"Maximum {MAX_PARALLEL_TRADES} parallel trades actively running"
                elif pending_locked and s.sessionType == "SEMI_AUTO":
                    msg = f"{len(pending_locked)} auto-locked pick(s) ready for confirmation"
                else:
                    msg = "No saved opportunity fits this session right now" if candidates else \
                        "No live saved opportunities for this session's underlyings"
                state_name = "PICK_READY" if (pending_locked and s.sessionType == "SEMI_AUTO") else "WAITING"
                return self._loop_response(
                    s, now, cap, state_name, msg, picks=live, locked_picks=pending_locked,
                    active_trade_ids=active_ids, pick_to_trade=pick_to_trade,
                    candidates=len(candidates), excluded=excluded,
                )
            n = len(live)
            return self._loop_response(
                s, now, cap, "PICK_READY", f"{n} trade{'s' if n != 1 else ''} to take",
                picks=live, locked_picks=pending_locked, active_trade_ids=active_ids,
                pick_to_trade=pick_to_trade, candidates=len(candidates), excluded=excluded,
            )

    # ───────────────────────── trade lock ─────────────────────────
    async def lock(self, db: AsyncSession, session_id: int, pick_id: int) -> SessionPickResponse:
        """Trade Lock: valid only while the pick is OFFERED and its opportunity has not expired. Idempotent once LOCKED."""
        async with self._lock_for(session_id):
            s = await self._load(db, session_id)
            pick = await self.picks.get_by_id(db, pick_id)
            if not pick or pick.sessionId != session_id:
                raise NotFoundException(message=f"Pick {pick_id} not found in session {session_id}")
            now = datetime.now(UTC)
            open_picks = await self.picks.open_picks(db, session_id)
            locked = [p for p in open_picks if p.pickState == "LOCKED"]
            cap, active_ids, pick_to_trade, _ = await self._session_commitments(db, s, locked)

            if pick.pickState == "LOCKED":
                return self.pick_response(pick, now, trade_id=pick_to_trade.get(pick.id))
            if pick.pickState != "OFFERED":
                raise ConflictException(message=f"Pick is {pick.pickState}; the window has closed",
                                        error={"code": "PICK_NOT_OFFERED", "pickState": pick.pickState})
            if _utc(pick.expiresAt) <= now:
                raise ConflictException(message="Too late: this opportunity has expired",
                                        error={"code": "PICK_EXPIRED"})
            if s.sessionStatus != "ACTIVE":
                raise ConflictException(message=f"Session is {s.sessionStatus}", error={"code": "SESSION_NOT_ACTIVE"})
            if s.closeAt is not None and now >= _utc(s.closeAt):
                raise ConflictException(message="Session trading hours are over", error={"code": "SESSION_HOURS_OVER"})
            if len(active_ids) >= MAX_PARALLEL_TRADES:
                raise ConflictException(
                    message=f"Session already has {MAX_PARALLEL_TRADES} parallel active trades running",
                    error={"code": "MAX_PARALLEL_TRADES", "maxParallelTrades": MAX_PARALLEL_TRADES},
                )
            if cap.lossUsed >= cap.maxLossAmount:
                raise ConflictException(message="Session loss limit reached", error={"code": "HALTED"})
            if float(pick.capitalRequired) > cap.availableCapital + 0.005:
                raise ConflictException(message="Not enough free capital for this pick",
                                        error={"code": "INSUFFICIENT_CAPITAL"})
            if float(pick.riskAmount) > cap.remainingLossBudget + 0.005:
                raise ConflictException(message="This pick exceeds the remaining session loss budget",
                                        error={"code": "LOSS_BUDGET"})
            pick.pickState, pick.lockedAt = "LOCKED", now
            pick.lockedPrice = await self.opportunities.live_premium(db, pick.instrumentKey)
            await db.flush()
            return self.pick_response(pick, now, trade_id=pick_to_trade.get(pick.id))

    # ───────────────────────── history ─────────────────────────
    async def search_picks(
        self, db: AsyncSession, session_id: int, filter_obj: SessionPickSearchFilter
    ) -> PageResult[SessionPickResponse]:
        s = await self._load(db, session_id)
        now = datetime.now(UTC)
        _, _, pick_to_trade, _ = await self._session_commitments(db, s, [])
        page = await self.picks.search(db, session_id, filter_obj)
        return PageResult(
            list=[self.pick_response(p, now, trade_id=pick_to_trade.get(p.id)) for p in page.list],
            page=page.page, limit=page.limit,
            totalPages=page.totalPages, totalItems=page.totalItems,
        )


session_loop_service = SessionLoopService()
