"""
Learning loop = the AUTOPSY SUB-AGENT of each session manager (plain code, not an LLM / LangGraph agent). Every
finished trade gets an autopsy by the manager that ran its session, and the results change what THAT manager does next.

  on_trade_closed()  autopsy (autopsy_agent.py) -> the manager's setup scorecard (auto pause / un-pause) -> guard
                     proposals for that manager
  view_for(code)     one manager's picture, read every tick by its sessions' loop and trade pilots:
                     {"paused": {setup: reason}, "guards": {setup: [applied guards]}, "scorecards": {setup: {...}}}
  view()             all managers merged (same shape) plus "managers": {code: view}; read by the opportunity engine,
                     which serves every session (a setup belongs to one trader, so merging loses nothing)
  apply / reject     a guard; applied guards are enforced, and mirrored as an enabled AUTOPSY rule in the Rules module
  resume             a paused setup by hand (its window then restarts from now)

One uvicorn worker, so the in-memory view is the single source the hot paths read; it is rebuilt from the database
after every write and on first use.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.events import notify as nt
from app.core.exception.app_exceptions import ConflictException, NotFoundException
from app.core.logging.logger import logger
from app.core.pagination.page_result import PageResult
from app.modules.autopsy.entity.setup_guard_entity import SetupGuard
from app.modules.autopsy.entity.setup_scorecard_entity import SetupScorecard
from app.modules.autopsy.entity.trade_autopsy_entity import TradeAutopsy
from app.modules.autopsy.repository.learning_repository import LearningRepository
from app.modules.autopsy.schema.learning_schema import (
    AutopsySearchFilter,
    GuardSearchFilter,
    ScorecardSearchFilter,
    SetupGuardResponse,
    SetupScorecardResponse,
    TradeAutopsyResponse,
)
from app.modules.autopsy.service import learning_rules as lr
from app.modules.autopsy.service.autopsy_agent import autopsy

RULE_TYPE = {"WITH_TREND_ONLY": "MARKET_REGIME", "NO_LATE_ENTRY": "TIME", "EARLIER_BREAKEVEN": "RISK",
             "MIN_TARGET_PCT": "FILTER"}
RULE_ACTION = {"WITH_TREND_ONLY": "BLOCK", "NO_LATE_ENTRY": "BLOCK", "EARLIER_BREAKEVEN": "REQUIRE",
               "MIN_TARGET_PCT": "BLOCK"}


def _policy(setup: str) -> str | None:
    from app.modules.opportunity_finder.service.setups import SETUP_POLICY  # lazy: heavy module

    return SETUP_POLICY.get(setup)


def _page(page: PageResult[Any], model: Any) -> PageResult[Any]:
    return PageResult(list=[model.model_validate(x) for x in page.list], page=page.page, limit=page.limit,
                      totalPages=page.totalPages, totalItems=page.totalItems)


def _empty() -> dict[str, Any]:
    return {"paused": {}, "guards": {}, "scorecards": {}}


# trader_presets is imported lazily: importing the trades package here would close an import cycle
# (trades -> opportunities run_service -> learning_service).
def normalize_trader_code(code: str | None) -> str | None:
    from app.modules.trade_history.service.trader_presets import normalize_trader_code as f

    return f(code)


def manager_name(code: str | None) -> str:
    from app.modules.trade_history.service.trader_presets import manager_name as f

    return f(code)


def manager_of(setup: str | None, manager_code: str | None = None) -> str:
    """The session manager an autopsy row belongs to: the one given, else the trader that owns the setup."""
    from app.modules.trade_history.service.trader_presets import assign_trader_for_opportunity

    return normalize_trader_code(manager_code) or assign_trader_for_opportunity(setup)


class LearningService:
    def __init__(self, repo: LearningRepository | None = None):
        self.repo = repo or LearningRepository()
        self._view: dict[str, Any] = {**_empty(), "managers": {}}
        self._loaded = False

    # ───────────────────────── view read by the hot paths ─────────────────────────
    def view(self) -> dict[str, Any]:
        """All managers merged: for the opportunity engine, which serves every session."""
        return self._view

    def view_for(self, manager_code: str | None) -> dict[str, Any]:
        """One session manager's autopsy sub-agent view: only what its own trades taught it."""
        code = normalize_trader_code(manager_code)
        return (self._view["managers"].get(code) or _empty()) if code else self._view

    async def ensure_loaded(self, db: AsyncSession) -> None:
        if not self._loaded:
            try:
                await self._refresh(db)
            except Exception as e:  # noqa: BLE001 -- a missing table must never stop trading
                logger.warning(f"[LEARNING] view not loaded: {type(e).__name__}: {e}")

    async def _refresh(self, db: AsyncSession) -> None:
        cards = await self.repo.all_scorecards(db)
        guards = await self.repo.applied_guards(db)
        view: dict[str, Any] = {**_empty(), "managers": {}}

        def into(code: str) -> list[dict[str, Any]]:
            return [view, view["managers"].setdefault(code, _empty())]

        for c in cards:
            for v in into(c.managerCode):
                v["scorecards"][c.setup] = {"closedTrades": c.closedTrades, "netPnl": float(c.netPnl),
                                            "avgR": float(c.avgR), "winRatePct": float(c.winRatePct),
                                            "scoreStatus": c.scoreStatus}
                if c.scoreStatus == "PAUSED":
                    v["paused"][c.setup] = c.statusReason or "paused"
        for g in guards:
            for v in into(g.managerCode):
                v["guards"].setdefault(g.setup, []).append({"id": g.id, "guardType": g.guardType,
                                                           "params": dict(g.params or {}), "text": g.text})
        self._view, self._loaded = view, True

    # ───────────────────────── a trade finished ─────────────────────────
    async def on_trade_closed(self, db: AsyncSession, trade: Any, pick_risks: list[Any] | None = None,
                              exchange: str | None = None, manager_code: str | None = None) -> TradeAutopsy | None:
        """Autopsy + learning for one EXITED trade, by the autopsy sub-agent of `manager_code` (the session's
        manager; default: the trader that owns the setup). Idempotent: a trade is autopsied once."""
        existing = await self.repo.autopsy_for_trade(db, trade.id)
        if existing is not None:
            return existing
        tel = trade.marketTelemetry or {}
        entry = float(trade.entryAt)
        data = autopsy({
            "entryAt": entry, "initialStop": trade.initialStop, "initialTarget": trade.initialTarget,
            "exitPrice": trade.exitPrice, "peakPrice": trade.peakPrice, "troughPrice": trade.troughPrice,
            "grossPnl": trade.grossPnl, "netPnl": trade.netPnl, "charges": trade.charges,
            "exitReason": trade.exitReason, "strategy": trade.strategy, "enteredAt": trade.enteredAt,
            "exitedAt": trade.exitedAt, "exchange": exchange, "pickRisks": pick_risks,
            "traderCode": tel.get("traderCode"),
        })
        manager = manager_of(data["setup"], manager_code)
        planned_pct = round((float(trade.initialTarget) - entry) / entry * 100, 2) if entry > 0 else None
        row = TradeAutopsy(
            tradeId=trade.id, sessionId=trade.sessionId, setup=data["setup"], managerCode=manager,
            traderCode=data["traderCode"],
            underlyingCode=trade.underlyingCode, optionType=trade.optionType, outcome=data["outcome"],
            verdict=data["verdict"], rMultiple=data["rMultiple"], mfeR=data["mfeR"], maeR=data["maeR"],
            givebackPct=data["givebackPct"], netPnl=data["netPnl"], plannedTargetPct=planned_pct,
            tags=data["tags"], wentRight=data["wentRight"], wentWrong=data["wentWrong"], lessons=data["lessons"],
            details={k: data[k] for k in ("riskPerUnit", "plannedR", "minutesToCloseAtEntry", "heldMinutes",
                                          "exitReason", "grossPnl")},
            learning={},
        )
        await self.repo.save(db, row)
        row.learning = await self._learn(db, manager, data["setup"], trade.id)
        await db.flush()
        await self._refresh(db)
        return row

    async def _learn(self, db: AsyncSession, manager: str, setup: str, trade_id: int) -> dict[str, Any]:
        now = datetime.now(UTC)
        policy = _policy(setup)
        who = manager_name(manager)
        card = await self.repo.scorecard(db, manager, setup)
        if card is None:
            card = await self.repo.save(db, SetupScorecard(setup=setup, managerCode=manager, policy=policy,
                                                           scoreStatus="ACTIVE"))
        before = card.scoreStatus
        rows = await self.repo.autopsies_since(db, manager, setup, lr.window_start(now, card.resumedAt))
        sc = lr.scorecard([{"outcome": r.outcome, "netPnl": r.netPnl, "rMultiple": r.rMultiple} for r in rows])
        card.policy, card.closedTrades, card.wins, card.losses = policy, sc["closedTrades"], sc["wins"], sc["losses"]
        card.netPnl, card.avgR, card.winRatePct, card.expectancy = sc["netPnl"], sc["avgR"], sc["winRatePct"], \
            sc["expectancy"]
        card.scoreStatus, card.lastTradeId, card.updatedAt = sc["status"], trade_id, now
        if sc["status"] == "PAUSED":
            card.statusReason = sc["statusReason"]
            card.pausedAt = card.pausedAt if before == "PAUSED" else now
        else:
            card.statusReason = "back in profit inside the window" if before == "PAUSED" else None
            card.pausedAt = None

        guards = await self.repo.guards_for(db, manager, setup)
        blocked_types = {g.guardType for g in guards if g.guardState in ("PROPOSED", "APPLIED")} | {
            g.guardType for g in guards
            if g.guardState == "REJECTED" and g.decidedAt and g.decidedAt >= now - timedelta(days=lr.WINDOW_DAYS)}
        proposals = lr.guard_proposals(setup, policy, [
            {"tradeId": r.tradeId, "tags": r.tags, "netPnl": float(r.netPnl),
             "plannedTargetPct": float(r.plannedTargetPct) if r.plannedTargetPct is not None else None}
            for r in rows], blocked_types)
        proposed: list[dict[str, Any]] = []
        for p in proposals:
            g = await self.repo.save(db, SetupGuard(setup=setup, managerCode=manager, guardType=p["guardType"],
                                                    tag=p["tag"],
                                                    params=p["params"], text=p["text"], evidence=p["evidence"],
                                                    guardState="PROPOSED"))
            await self._mirror_rule(db, g, enabled=False)
            if settings.AUTOPSY_AUTO_APPLY_GUARDS:
                await self._decide(db, g, "APPLIED")
            proposed.append({"id": g.id, "text": g.text, "guardState": g.guardState})
        await db.flush()
        if card.scoreStatus == "PAUSED" and before != "PAUSED":
            await nt.notify(nt.LEARNING, f"{who} · autopsy paused {setup}",
                            f"{card.statusReason}. {who}'s sessions stop taking it.",
                            severity="warning", data={"setup": setup, "managerCode": manager})
        for p in proposed:
            await nt.notify(nt.LEARNING,
                            f"{who} · autopsy {'applied' if p['guardState'] == 'APPLIED' else 'proposed'} a rule",
                            p["text"], data={"setup": setup, "guardId": p["id"], "managerCode": manager})
        return {"managerCode": manager, "scorecardBefore": before, "scorecardAfter": card.scoreStatus, "statusReason": card.statusReason,
                "closedTrades": card.closedTrades, "netPnl": float(card.netPnl), "avgR": float(card.avgR),
                "guardsProposed": proposed}

    # ───────────────────────── rules module mirror ─────────────────────────
    async def _mirror_rule(self, db: AsyncSession, g: SetupGuard, enabled: bool) -> None:
        """Keep an AUTOPSY rule in the Rules module in step with the guard. Best effort: the guard is the source."""
        try:
            from app.modules.strategies.schema.rule_schema import RuleCreate, RuleUpdate
            from app.modules.strategies.service.rule_service import RuleService

            rules = RuleService()
            note = (f"{g.text} Learned from {g.evidence.get('trades')} trades in {g.evidence.get('windowDays')} days "
                    f"(net ₹{g.evidence.get('netPnl'):,.0f}). Enforced by the learning module while APPLIED.")
            if g.ruleId is None:
                created = await rules.create(db, RuleCreate(
                    code=f"AUTOPSY-{g.id}", name=f"Autopsy ({manager_name(g.managerCode)}): {g.setup} {g.guardType}"[:150],
                    ruleKind="CONDITION_BLOCK", ruleType=RULE_TYPE[g.guardType], action=RULE_ACTION[g.guardType],
                    priority="MEDIUM", appliesTo={"setups": [g.setup], "managers": [g.managerCode], "markets": ["ALL"]},
                    conditionText=note,
                    content={"guardId": g.id, "guardType": g.guardType, "params": g.params},
                    evidence=g.evidence, provenance={"source": "AUTOPSY", "guardId": g.id, "managerCode": g.managerCode},
                    changeNote=f"Proposed by {manager_name(g.managerCode)}'s autopsy sub-agent"))
                g.ruleId = created.id
            await rules.update(db, g.ruleId, RuleUpdate(
                enabled=enabled, changeNote=f"Guard {g.guardState.lower()}"))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[LEARNING] rule mirror for guard {g.id}: {type(e).__name__}: {e}")

    async def _decide(self, db: AsyncSession, g: SetupGuard, state: str) -> None:
        g.guardState, g.decidedAt = state, datetime.now(UTC)
        await db.flush()
        await self._mirror_rule(db, g, enabled=state == "APPLIED")

    async def apply_guard(self, db: AsyncSession, guard_id: int) -> SetupGuardResponse:
        return await self._set_guard(db, guard_id, "APPLIED")

    async def reject_guard(self, db: AsyncSession, guard_id: int) -> SetupGuardResponse:
        return await self._set_guard(db, guard_id, "REJECTED")

    async def _set_guard(self, db: AsyncSession, guard_id: int, state: str) -> SetupGuardResponse:
        g = await self.repo.guard(db, guard_id)
        if g is None:
            raise NotFoundException(message=f"Guard {guard_id} not found")
        if g.guardState == state:
            return SetupGuardResponse.model_validate(g)
        if state == "APPLIED" and g.guardState == "REJECTED":
            raise ConflictException(message="This guard was rejected; a new one is proposed if the pattern repeats",
                                    error={"code": "GUARD_REJECTED"})
        await self._decide(db, g, state)
        await self._refresh(db)
        return SetupGuardResponse.model_validate(g)

    async def resume_setup(self, db: AsyncSession, setup: str, manager_code: str | None = None) -> SetupScorecardResponse:
        manager = manager_of(setup, manager_code)
        card = await self.repo.scorecard(db, manager, setup)
        if card is None:
            raise NotFoundException(message=f"No {manager_name(manager)} scorecard for {setup}")
        now = datetime.now(UTC)
        card.scoreStatus, card.statusReason, card.pausedAt, card.resumedAt, card.updatedAt = (
            "ACTIVE", "resumed by hand: counting starts again from now", None, now, now)
        card.closedTrades = card.wins = card.losses = 0
        card.netPnl = card.avgR = card.winRatePct = card.expectancy = 0
        await db.flush()
        await self._refresh(db)
        return SetupScorecardResponse.model_validate(card)

    # ───────────────────────── reads ─────────────────────────
    async def autopsy_for_trade(self, db: AsyncSession, trade_id: int) -> TradeAutopsyResponse:
        a = await self.repo.autopsy_for_trade(db, trade_id)
        if a is None:
            raise NotFoundException(message=f"No autopsy for trade {trade_id} (it is written when the trade exits)")
        return TradeAutopsyResponse.model_validate(a)

    async def autopsies_by_trade(self, db: AsyncSession, session_id: int) -> dict[int, TradeAutopsy]:
        page = await self.repo.search_autopsies(db, AutopsySearchFilter(sessionId=session_id, page=0, limit=100))
        return {a.tradeId: a for a in page.list}

    async def search_autopsies(self, db: AsyncSession, f: AutopsySearchFilter) -> PageResult[TradeAutopsyResponse]:
        return _page(await self.repo.search_autopsies(db, f), TradeAutopsyResponse)

    async def search_scorecards(self, db: AsyncSession, f: ScorecardSearchFilter) -> PageResult[SetupScorecardResponse]:
        return _page(await self.repo.search_scorecards(db, f), SetupScorecardResponse)

    async def search_guards(self, db: AsyncSession, f: GuardSearchFilter) -> PageResult[SetupGuardResponse]:
        return _page(await self.repo.search_guards(db, f), SetupGuardResponse)


learning_service = LearningService()
