"""
Unit & flow tests for `TradeService` and `SessionLoopService` automation modes:
  - `preview_sizing` recalculates suggested lots as `entryAt` changes
  - `MAX_PARALLEL_TRADES = 3` enforced per session
  - `routeThroughUpstox = True` places Upstox BUY on entry and SELL on exit
  - `SEMI_AUTO` auto-selects and auto-locks the #1 best opportunity
  - `FULL_AUTO` auto-selects, auto-locks, and auto-enters the #1 best opportunity
  - Exiting a trade updates `TradingSession.realizedPnl` and frees the parallel slot
"""
import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ConflictException
from app.modules.sessions.entity.session_pick_entity import SessionPick
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.service.session_loop_service import SessionLoopService
from app.modules.trades.entity.trade_entity import ActiveTrade
from app.modules.trades.schema.trade_schema import TradeCreateRequest, TradeExitRequest
from app.modules.trades.service.trade_service import TradeService

NOW = lambda: datetime.now(UTC)  # noqa: E731
TODAY = lambda: datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()  # noqa: E731


class FakeDb:
    async def flush(self):
        pass

    async def commit(self):
        pass


class FakeTradeRepo:
    def __init__(self):
        self.rows: list[ActiveTrade] = []

    async def get_by_id(self, db, tid: int):
        return next((t for t in self.rows if t.id == tid), None)

    async def get_by_pick_id(self, db, pid: int):
        return next((t for t in self.rows if t.pickId == pid), None)

    async def running_for_session(self, db, sid: int):
        return [t for t in self.rows if t.sessionId == sid and t.tradeState == "RUNNING"]

    async def all_for_session(self, db, sid: int):
        return [t for t in self.rows if t.sessionId == sid]

    async def running_ids_today(self, db, day_start):
        return [t.id for t in self.rows if t.tradeState == "RUNNING"]

    async def save(self, db, entity: ActiveTrade):
        if not getattr(entity, "id", None):
            entity.id = len(self.rows) + 1
            entity.createdAt = NOW()
            entity.status = EntityStatus.ACTIVE
            self.rows.append(entity)
        return entity


class FakeOrderClient:
    def __init__(self):
        self.calls: list[dict] = []

    async def place_order(self, session, user_id, instrument_key, quantity, transaction_type, order_type="MARKET", price=0.0, tag=""):
        order_id = f"ORD-{transaction_type}-{len(self.calls) + 1}"
        self.calls.append({
            "userId": user_id,
            "instrumentKey": instrument_key,
            "quantity": quantity,
            "transactionType": transaction_type,
            "price": price,
            "orderId": order_id,
        })
        return {"ok": True, "orderId": order_id, "status": "PLACED", "error": None}


class FakeSessions:
    def __init__(self, s: TradingSession):
        self.s = s

    async def get_by_id(self, db, sid: int):
        return self.s if self.s.id == sid else None


class FakePicks:
    def __init__(self):
        self.rows: list[SessionPick] = []

    async def open_picks(self, db, sid: int):
        return [p for p in self.rows if p.sessionId == sid and p.pickState in ("OFFERED", "LOCKED")]

    async def offered_opportunity_ids(self, db, sid: int):
        return {p.opportunityId for p in self.rows if p.sessionId == sid}

    async def save(self, db, p: SessionPick):
        p.id = len(self.rows) + 1
        p.createdAt = NOW()
        self.rows.append(p)
        return p

    async def get_by_id(self, db, pid: int):
        return next((p for p in self.rows if p.id == pid), None)


class FakeOpps:
    def __init__(self, items=None, price=20.0):
        self.items = items or []
        self.price = price

    async def saved_candidates(self, db, codes, max_age):
        return [o for o in self.items if o["underlyingCode"] in codes]

    async def live_premium(self, db, instrument_key):
        return self.price


def make_opp(i=1, **kw):
    base = {
        "id": i,
        "ref": f"OP-NIFTY-{i}",
        "underlyingCode": "NIFTY",
        "optionType": "CE",
        "strike": 25000.0 + i * 50,
        "expiry": "2026-11-12",
        "entry": 20.0,
        "stop": 15.0,
        "target": 30.0,
        "confidence": 85,
        "rewardRisk": 2.0,
        "strategy": "ORB",
        "reasons": ["Breakout"],
        "risks": ["Theta"],
        "instrumentKey": f"NSE_FO|{i}",
        "exchange": "NSE",
        "lotUnits": 65,
        "profitMarginPct": 50.0,
        "createdAt": (NOW() - timedelta(seconds=5)).isoformat(),
        "validUntil": (NOW() + timedelta(minutes=10)).isoformat(),
    }
    base.update(kw)
    return base


def test_preview_sizing_and_max_3_parallel_trades_and_upstox_orders(monkeypatch):
    import sys
    from app.modules.opportunities.service import run_service as opp_run_mod
    from app.modules.trades.engine import trade_pilot_runner as pilot_mod
    import app.modules.sessions.service.session_loop_service  # noqa: F401
    import app.modules.trades.service.trade_service  # noqa: F401

    sls_mod = sys.modules["app.modules.sessions.service.session_loop_service"]
    ts_mod = sys.modules["app.modules.trades.service.trade_service"]

    async def go():
        s = TradingSession(
            name="Live Session",
            tradeDate=TODAY(),
            userId=1,
            capital=200000,
            maxLossPercentage=5,  # 10,000 loss budget
            scope="INDEX",
            underlyings=["NIFTY"],
            commodityItems=[],
            sessionType="MANUAL",
            routeThroughUpstox=True,
            sessionStatus="ACTIVE",
            realizedPnl=0,
            startAt=NOW() - timedelta(hours=1),
            closeAt=NOW() + timedelta(hours=4),
        )
        s.id = 10
        picks_repo = FakePicks()
        opps = FakeOpps([make_opp(1), make_opp(2), make_opp(3), make_opp(4)], price=20.0)
        loop_svc = SessionLoopService(FakeSessions(s), picks_repo, opps)

        trade_repo = FakeTradeRepo()
        order_client = FakeOrderClient()
        t_svc = TradeService(repo=trade_repo, order_client=order_client)

        monkeypatch.setattr(sls_mod, "session_loop_service", loop_svc)
        monkeypatch.setattr(ts_mod, "trade_service", t_svc)
        monkeypatch.setattr(pilot_mod, "start", lambda tid: None)
        monkeypatch.setattr(pilot_mod, "stop", lambda tid: None)
        monkeypatch.setattr(pilot_mod, "publish_snapshot", lambda tid, snap: None)

        async def fake_live_px(session, key, timeout=1.5):
            return opps.price

        async def fake_candles(session, key, trade_date=None, timeout=3.0):
            return []

        async def fake_win_rate(session, code, strat, conf):
            return 85.0

        monkeypatch.setattr(opp_run_mod.opportunity_run_service, "live_premium", fake_live_px)
        monkeypatch.setattr(opp_run_mod.opportunity_run_service, "option_candles_1m", fake_candles)
        monkeypatch.setattr(opp_run_mod.opportunity_run_service, "resolve_win_rate_pct", fake_win_rate)

        # 1. Tick session loop -> 4 offers
        snap = await loop_svc.tick(FakeDb(), 10)
        assert len(snap.picks) == 4

        # 2. Preview sizing at entryAt=20 vs entryAt=22
        p1 = snap.picks[0]
        sz20 = await t_svc.preview_sizing(FakeDb(), 10, p1.id, entry_at=20.0)
        sz22 = await t_svc.preview_sizing(FakeDb(), 10, p1.id, entry_at=22.0)
        assert sz20.canEnter and sz20.suggestedLots >= 1
        assert sz22.maxLotsByRisk <= sz20.maxLotsByRisk  # higher entry against same stop = higher risk/lot

        # 3. Enter 3 parallel trades -> succeeds and places 3 Upstox BUY orders
        t1 = await t_svc.enter_trade(FakeDb(), TradeCreateRequest(sessionId=10, pickId=snap.picks[0].id, entryAt=20.0, lots=1))
        t2 = await t_svc.enter_trade(FakeDb(), TradeCreateRequest(sessionId=10, pickId=snap.picks[1].id, entryAt=20.0, lots=1))
        t3 = await t_svc.enter_trade(FakeDb(), TradeCreateRequest(sessionId=10, pickId=snap.picks[2].id, entryAt=20.0, lots=1))
        assert t1.entryOrderId == "ORD-BUY-1" and t1.brokerStatus == "PLACED"
        assert len(order_client.calls) == 3

        # 4. Attempting a 4th parallel trade is blocked with MAX_PARALLEL_TRADES (409)
        with pytest.raises(ConflictException) as exc:
            await t_svc.enter_trade(FakeDb(), TradeCreateRequest(sessionId=10, pickId=snap.picks[3].id, entryAt=20.0, lots=1))
        assert exc.value.error["code"] == "MAX_PARALLEL_TRADES"

        # 5. Live tick on Trade 1: price reaches 28 (80% of 20->30) -> SL ratchets to 25.0
        opps.price = 28.0
        tick_snap = await t_svc.tick(FakeDb(), t1.id)
        assert tick_snap.trade.currentStop == 25.0
        assert tick_snap.trade.tradeState == "RUNNING"

        # 6. Manual exit on Trade 1 -> places Upstox SELL order, updates session realizedPnl, and frees slot!
        exited = await t_svc.manual_exit(FakeDb(), t1.id, TradeExitRequest(exitPrice=29.0))
        assert exited.tradeState == "EXITED"
        assert exited.exitOrderId == "ORD-SELL-4"
        assert s.realizedPnl > 0

        # 7. Now slot is free (2 running), so 4th trade can enter!
        t4 = await t_svc.enter_trade(FakeDb(), TradeCreateRequest(sessionId=10, pickId=snap.picks[3].id, entryAt=20.0, lots=1))
        assert t4.tradeState == "RUNNING"

    asyncio.run(go())


def test_semi_auto_and_full_auto_session_modes(monkeypatch):
    import sys
    from app.modules.opportunities.service import run_service as opp_run_mod
    from app.modules.trades.engine import trade_pilot_runner as pilot_mod
    import app.modules.sessions.service.session_loop_service  # noqa: F401
    import app.modules.trades.service.trade_service  # noqa: F401

    sls_mod = sys.modules["app.modules.sessions.service.session_loop_service"]
    ts_mod = sys.modules["app.modules.trades.service.trade_service"]

    async def go():
        monkeypatch.setattr(pilot_mod, "start", lambda tid: None)
        monkeypatch.setattr(pilot_mod, "stop", lambda tid: None)
        monkeypatch.setattr(pilot_mod, "publish_snapshot", lambda tid, snap: None)
        monkeypatch.setattr(opp_run_mod.opportunity_run_service, "live_premium", lambda db, k, timeout=1.5: asyncio.sleep(0, 20.0))
        monkeypatch.setattr(opp_run_mod.opportunity_run_service, "resolve_win_rate_pct", lambda db, c, st, cf: asyncio.sleep(0, 80.0))

        # A) SEMI_AUTO: auto-selects #1 pick and locks it
        s_semi = TradingSession(
            name="Semi", tradeDate=TODAY(), userId=1, capital=100000, maxLossPercentage=3, scope="INDEX",
            underlyings=["NIFTY"], commodityItems=[], sessionType="SEMI_AUTO", routeThroughUpstox=False,
            sessionStatus="ACTIVE", realizedPnl=0, startAt=NOW() - timedelta(hours=1), closeAt=NOW() + timedelta(hours=2),
        )
        s_semi.id = 21
        picks_semi = FakePicks()
        opps_semi = FakeOpps([make_opp(1, confidence=65), make_opp(2, confidence=90)], price=20.0)
        loop_semi = SessionLoopService(FakeSessions(s_semi), picks_semi, opps_semi)
        t_svc_semi = TradeService(repo=FakeTradeRepo(), order_client=FakeOrderClient())
        monkeypatch.setattr(sls_mod, "session_loop_service", loop_semi)
        monkeypatch.setattr(ts_mod, "trade_service", t_svc_semi)

        r_semi = await loop_semi.tick(FakeDb(), 21)
        assert len(r_semi.lockedPicks) == 1
        assert r_semi.lockedPicks[0].opportunityId == 2  # highest ranked opportunity auto-locked!
        assert r_semi.lockedPicks[0].pickState == "LOCKED"
        assert r_semi.capital.activeTradesCount == 0  # awaiting confirmation in SEMI_AUTO

        # B) FULL_AUTO: auto-selects #1 pick, auto-locks it, AND auto-enters the trade!
        s_full = TradingSession(
            name="Full", tradeDate=TODAY(), userId=1, capital=100000, maxLossPercentage=3, scope="INDEX",
            underlyings=["NIFTY"], commodityItems=[], sessionType="FULL_AUTO", routeThroughUpstox=False,
            sessionStatus="ACTIVE", realizedPnl=0, startAt=NOW() - timedelta(hours=1), closeAt=NOW() + timedelta(hours=2),
        )
        s_full.id = 22
        picks_full = FakePicks()
        opps_full = FakeOpps([make_opp(10, confidence=88)], price=20.0)
        loop_full = SessionLoopService(FakeSessions(s_full), picks_full, opps_full)
        t_svc_full = TradeService(repo=FakeTradeRepo(), order_client=FakeOrderClient())
        monkeypatch.setattr(sls_mod, "session_loop_service", loop_full)
        monkeypatch.setattr(ts_mod, "trade_service", t_svc_full)

        r_full = await loop_full.tick(FakeDb(), 22)
        assert r_full.capital.activeTradesCount == 1
        assert len(r_full.capital.activeTradeIds) == 1

    asyncio.run(go())
