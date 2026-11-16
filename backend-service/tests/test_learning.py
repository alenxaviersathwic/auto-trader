"""Autopsy agent, setup scorecards, guards and their enforcement; session manager verdicts. No DB: fakes."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.modules.learning.service import autopsy_agent as aa
from app.modules.learning.service import learning_rules as lr
from app.modules.learning.service.learning_service import LearningService
from app.modules.opportunities.service import setups as setup_detector
from app.modules.sessions.service import session_manager as sm

T0 = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)  # 10:30 IST


def trade(**kw):
    base = {"entryAt": 100, "initialStop": 90, "initialTarget": 130, "exitPrice": 89, "peakPrice": 101,
            "troughPrice": 89, "grossPnl": -715, "netPnl": -800, "charges": 85, "exitReason": "STOP_HIT",
            "strategy": "NOISE_BREAKOUT", "enteredAt": T0, "exitedAt": T0 + timedelta(minutes=20),
            "exchange": "NSE", "pickRisks": [], "traderCode": "FLOW_MOMENTUM_TRADER"}
    base.update(kw)
    return base


# ───────────────────────── autopsy ─────────────────────────
def test_autopsy_measures_in_r_and_names_what_went_wrong():
    a = aa.autopsy(trade())
    assert (a["outcome"], a["verdict"]) == ("LOSS", "NEVER_WORKED")
    assert a["rMultiple"] == -1.1 and a["mfeR"] == 0.1 and a["maeR"] == 1.1
    assert a["tags"] == ["NEVER_WORKED"] and a["heldMinutes"] == 20.0
    assert any("never moved" in w.lower() for w in a["wentWrong"]) and a["lessons"]


def test_autopsy_verdicts():
    assert aa.autopsy(trade(exitPrice=125, peakPrice=126, grossPnl=1700, netPnl=1600,
                            exitReason="TRAILING_STOP_HIT"))["verdict"] == "RAN_TO_TARGET"
    gave = aa.autopsy(trade(peakPrice=118, exitPrice=95, grossPnl=-300, netPnl=-385))
    assert gave["verdict"] == "GAVE_BACK_WINNER" and "GAVE_BACK" in gave["tags"]
    fees = aa.autopsy(trade(exitPrice=100.5, peakPrice=104, grossPnl=30, netPnl=-55))
    assert fees["verdict"] == "FEES_ATE_PROFIT" and "FEES_ATE_PROFIT" in fees["tags"]
    kept = aa.autopsy(trade(exitPrice=112, peakPrice=114, grossPnl=900, netPnl=815, exitReason="TRAILING_STOP_HIT"))
    assert kept["verdict"] == "PROTECTED_PROFIT" and kept["tags"] == []


def test_autopsy_context_tags():
    late = aa.autopsy(trade(enteredAt=datetime(2026, 11, 16, 9, 15, tzinfo=UTC)))  # 14:45 IST
    assert "LATE_ENTRY" in late["tags"] and late["minutesToCloseAtEntry"] == 45
    assert "LATE_ENTRY" not in aa.autopsy(trade(strategy="LATE_DAY_MOMENTUM",
                                                enteredAt=datetime(2026, 11, 16, 9, 15, tzinfo=UTC)))["tags"]
    assert "AGAINST_TREND" in aa.autopsy(trade(pickRisks=["Against the bullish trend"]))["tags"]
    assert aa.autopsy(trade(exitPrice=125, grossPnl=1700, netPnl=1600, pickRisks=["Against the trend"]))["tags"] == []


# ───────────────────────── scorecard + guards ─────────────────────────
def test_scorecard_pauses_only_on_a_net_loss_with_enough_trades():
    loss = {"outcome": "LOSS", "netPnl": -500, "rMultiple": -1}
    win = {"outcome": "WIN", "netPnl": 3000, "rMultiple": 4}
    assert lr.scorecard([loss] * 4)["status"] == "ACTIVE"  # too few trades
    paused = lr.scorecard([loss] * 5)
    assert paused["status"] == "PAUSED" and "5 trades" in paused["statusReason"]
    momentum = lr.scorecard([loss] * 5 + [win])  # 17% win rate but net positive: a momentum setup doing its job
    assert momentum["status"] == "ACTIVE" and momentum["winRatePct"] == 16.7


def test_guard_proposals_need_three_repeats_and_fit_the_setup():
    rows = [{"tradeId": i, "tags": ["AGAINST_TREND", "GAVE_BACK"], "netPnl": -400, "plannedTargetPct": 20}
            for i in range(3)]
    got = {g["guardType"]: g for g in lr.guard_proposals("NOISE_BREAKOUT", "CORE", rows, set())}
    assert set(got) == {"WITH_TREND_ONLY", "EARLIER_BREAKEVEN"}
    assert got["WITH_TREND_ONLY"]["evidence"]["tradeIds"] == [0, 1, 2]
    assert lr.guard_proposals("NOISE_BREAKOUT", "CORE", rows[:2], set()) == []
    assert lr.guard_proposals("NOISE_BREAKOUT", "CORE", rows, {"WITH_TREND_ONLY", "EARLIER_BREAKEVEN"}) == []
    fib = {g["guardType"] for g in lr.guard_proposals("FIB_GOLDEN_POCKET", "CONFIRMED", rows, set())}
    assert fib == {"WITH_TREND_ONLY"}  # no momentum trail to move on a Fib trade
    fees = [{"tradeId": i, "tags": ["FEES_ATE_PROFIT"], "netPnl": -50, "plannedTargetPct": 8} for i in range(3)]
    assert lr.guard_proposals("INSIDE_BAR", "CORE", fees, set())[0]["params"] == {"minTargetPct": 12.0}


def test_guards_and_pauses_are_enforced():
    view = {"paused": {"INSIDE_BAR": "lost"}, "guards": {"NOISE_BREAKOUT": [
        {"guardType": "NO_LATE_ENTRY", "params": {"minutesToCloseMin": 60}},
        {"guardType": "WITH_TREND_ONLY", "params": {}},
        {"guardType": "MIN_TARGET_PCT", "params": {"minTargetPct": 12}},
        {"guardType": "EARLIER_BREAKEVEN", "params": {"beR": 1.0}}]}}
    assert "paused" in lr.engine_block(view, "INSIDE_BAR", 200)
    assert lr.engine_block(view, "NOISE_BREAKOUT", 45) and lr.engine_block(view, "NOISE_BREAKOUT", 90) is None
    assert lr.pick_block(view, "NOISE_BREAKOUT", ["Against the bullish trend"], 20)
    assert lr.pick_block(view, "NOISE_BREAKOUT", [], 10)
    assert lr.pick_block(view, "NOISE_BREAKOUT", [], 15) is None
    assert lr.trail_override(view, "NOISE_BREAKOUT", {"beR": 1.5, "fromR": 2, "trailR": 2})["beR"] == 1.0
    assert lr.engine_block(None, "INSIDE_BAR", 10) is None  # no view (backtests): never blocks


def test_live_engine_reads_the_learning_view_and_backtests_do_not():
    s = {"name": "NOISE_BREAKOUT", "side": "CE"}
    live = {"learning": {"paused": {"NOISE_BREAKOUT": "lost ₹4,000"}}, "session": {"minutesToClose": 200}}
    assert "paused" in setup_detector.policy_block(live, s)
    assert setup_detector.policy_block({"session": {"minutesToClose": 200}}, s) is None


# ───────────────────────── learning service (fake repository) ─────────────────────────
class FakeRepo:
    def __init__(self):
        self.autopsies, self.cards, self.guards, self.next = [], {}, [], 1

    async def save(self, db, e):
        if getattr(e, "id", None) is None:
            e.id, self.next = self.next, self.next + 1
            e.createdAt = datetime.now(UTC)
            from app.modules.learning.entity import SetupGuard, SetupScorecard, TradeAutopsy
            if isinstance(e, TradeAutopsy):
                self.autopsies.append(e)
            elif isinstance(e, SetupScorecard):
                self.cards[e.setup] = e
            elif isinstance(e, SetupGuard):
                self.guards.append(e)
        return e

    async def autopsy_for_trade(self, db, tid):
        return next((a for a in self.autopsies if a.tradeId == tid), None)

    async def autopsies_since(self, db, setup, since):
        return [a for a in self.autopsies if a.setup == setup and a.createdAt >= since]

    async def scorecard(self, db, setup):
        return self.cards.get(setup)

    async def all_scorecards(self, db):
        return list(self.cards.values())

    async def guard(self, db, gid):
        return next((g for g in self.guards if g.id == gid), None)

    async def guards_for(self, db, setup):
        return [g for g in self.guards if g.setup == setup]

    async def applied_guards(self, db):
        return [g for g in self.guards if g.guardState == "APPLIED"]


class FakeDb:
    async def flush(self):
        pass


def _trade(i, **kw):
    t = dict(id=i, sessionId=7, entryAt=100, initialStop=90, initialTarget=130, exitPrice=89, peakPrice=101,
             troughPrice=89, grossPnl=-715, netPnl=-800, charges=85, exitReason="STOP_HIT", strategy="NOISE_BREAKOUT",
             enteredAt=T0, exitedAt=T0 + timedelta(minutes=9), underlyingCode="NIFTY", optionType="CE",
             marketTelemetry={"traderCode": "FLOW_MOMENTUM_TRADER"})
    t.update(kw)
    return SimpleNamespace(**t)


def test_learning_service_pauses_a_losing_setup_and_proposes_guards():
    svc, repo, db = LearningService(FakeRepo()), None, FakeDb()
    repo = svc.repo
    for i in range(1, 6):
        row = asyncio.run(svc.on_trade_closed(db, _trade(i), ["Against the bullish trend"], "NSE"))
    assert row.verdict == "NEVER_WORKED" and row.learning["scorecardAfter"] == "PAUSED"
    assert repo.cards["NOISE_BREAKOUT"].closedTrades == 5
    assert "NOISE_BREAKOUT" in svc.view()["paused"]
    assert [g.guardType for g in repo.guards] == ["WITH_TREND_ONLY"]  # proposed once, after the 3rd repeat
    assert repo.guards[0].guardState == "PROPOSED" and not svc.view()["guards"]  # not enforced until applied
    assert asyncio.run(svc.on_trade_closed(db, _trade(5), [], "NSE")) is row  # a trade is autopsied once
    asyncio.run(svc.apply_guard(db, repo.guards[0].id))
    assert svc.view()["guards"]["NOISE_BREAKOUT"][0]["guardType"] == "WITH_TREND_ONLY"
    card = asyncio.run(svc.resume_setup(db, "NOISE_BREAKOUT"))
    assert card.scoreStatus == "ACTIVE" and "NOISE_BREAKOUT" not in svc.view()["paused"]


# ───────────────────────── session manager ─────────────────────────
def _pick(i, **kw):
    p = dict(id=i, strategy="NOISE_BREAKOUT", underlyingCode="NIFTY", strike=24500.0, optionType="CE", lots=1,
             expectedNet=600.0, riskAmount=500.0, capitalRequired=6500.0, confidence=72, risks=["IV is high"],
             pickState="OFFERED")
    p.update(kw)
    return SimpleNamespace(**p)


def test_best_suggestion_explains_itself_from_capital_risk_and_track_record():
    cap = SimpleNamespace(remainingLossBudget=2000.0, availableCapital=40000.0)
    view = {"scorecards": {"NOISE_BREAKOUT": {"closedTrades": 6, "netPnl": 2400.0, "avgR": 0.4}}}
    best = sm.best_suggestion([_pick(3), _pick(4)], cap, "LOW", "Proven setups only", view,
                              lambda s: "Flow & Momentum Trader", 1, 3)
    assert best["pickId"] == 3 and best["alternatives"] == 1
    assert best["headline"].startswith("Flow & Momentum Trader · NIFTY 24500 CE")
    assert "25% of the ₹2,000 loss budget" in best["reasons"][1]
    assert "6 trades, ₹+2,400, avg +0.40R" in best["reasons"][4]
    assert any("not a measured win rate" in c for c in best["cautions"])
    assert sm.best_suggestion([], cap, "LOW", "", view, str, 0, 3) is None


def test_judge_pick_and_batch_verdict():
    j = sm.judge_pick
    assert j("EXPIRED", {"outcome": "TARGET_HIT"}, None)["managerVerdict"] == "MISSED_WINNER"
    assert j("EXPIRED", {"outcome": "STOP_HIT"}, None)["managerVerdict"] == "GOOD_SKIP"
    assert j("EXPIRED", {"outcome": "EXPIRED"}, None)["managerVerdict"] == "NO_MOVE"
    assert j("EXPIRED", None, None)["managerVerdict"] == "PENDING"
    win = j("LOCKED", {"outcome": "TARGET_HIT"}, {"tradeState": "EXITED", "netPnl": 900, "exitReason": "TARGET_HIT",
                                                 "verdict": "RAN_TO_TARGET"})
    assert win["managerVerdict"] == "TAKEN_WIN" and "ran to target" in win["note"]
    b = sm.batch_verdict([win, j("EXPIRED", {"outcome": "TARGET_HIT"}, None), j("EXPIRED", {"outcome": "STOP_HIT"}, None)])
    assert b["verdict"] == "SUCCESS" and b["hits"] == 2 and b["taken"] == 1
    assert "missed 1 winner" in b["note"] and "skipped 1 loser" in b["note"]
    assert sm.batch_verdict([j("EXPIRED", {"outcome": "STOP_HIT"}, None)])["verdict"] == "FAILURE"
    assert sm.batch_verdict([j("EXPIRED", None, None)])["verdict"] == "PENDING"
