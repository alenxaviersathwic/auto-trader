import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import ConflictException, NotFoundException
from app.core.logging.logger import logger
from app.modules.research.service.run_service import run_service as research_run_service
from app.modules.suggestion.entity.suggestion_entity import SuggestionMaster, TradeSuggestion
from app.modules.suggestion.graph.builder import underlying_graph
from app.modules.suggestion.provider.underlying_config import get_config
from app.modules.suggestion.repository.suggestion_repository import (
    make_ref,
    risk_level,
    suggestion_master_repository as master_repo,
    suggestion_repository,
)
from app.modules.suggestion.schema.suggestion_schema import StartSuggestionRequest
from app.modules.suggestion.service import memory_service
from app.modules.suggestion.service.selector import select_underlyings

_IST = ZoneInfo("Asia/Kolkata")
ALL_IN_RESEARCH = 12  # select_underlyings count large enough to return every researched underlying


def _today() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


class SuggestionRunService:
    """
    Card-session model (replaces the old server-side loop):

      Start          -> one new suggestion_masters row per card (sessionNo = Nth start of the day)
      Iterate(id)    -> ONE pass for that card: gather -> menu -> AI -> validate -> save to
                        trade_suggestions, then the master's counters are updated
      Stop(id)/all   -> state = STOPPED; later iterate calls are no-ops

    The frontend drives the loop: it calls iterate on every RUNNING master one by one, waits
    loopGapSeconds, and repeats. A per-master lock stops two tabs iterating the same card at once.
    """

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}

    async def research_has_data(self, session: AsyncSession) -> bool:
        for utype in ("INDEX", "COMMODITY"):
            data = await research_run_service.get_latest_results(utype, session)
            if data.get("run"):
                return True
        return False

    # ───────────────────────── start / stop ─────────────────────────
    async def start(self, req: StartSuggestionRequest, session: AsyncSession) -> dict[str, Any]:
        """New master row per card. A card already RUNNING today is stopped and replaced by the new session."""
        if not await self.research_has_data(session):
            return {"started": False, "reason": "NO_RESEARCH_DATA",
                    "message": "Research Engine has no data yet. Run the Research Engine first.", "masters": []}
        today, now = _today(), datetime.now(UTC)
        await master_repo.close_stale_days(session, today, now)
        if req.underlyings:
            sel = await select_underlyings(session, ALL_IN_RESEARCH, ALL_IN_RESEARCH, req.underlyings)
            found = {c["underlyingCode"]: c for c in sel["items"]}
            # A card the user asked for that is missing from Research still gets a session (shown as missing).
            items = [found.get(code.upper()) or self._missing(code.upper()) for code in req.underlyings
                     if get_config(code.upper())]
        else:
            sel = await select_underlyings(session, req.indexCount, req.commodityCount)
            items = sel["items"]
        if not items:
            return {"started": False, "reason": "NO_UNDERLYINGS", "message": "No matching underlyings in Research.",
                    "masters": []}
        codes = [c["underlyingCode"] for c in items]
        for old in await master_repo.running(session, today, codes):
            old.state, old.stopReason, old.stoppedAt = "STOPPED", "REPLACED_BY_NEW_START", now
        params = req.model_dump(exclude={"underlyings"})
        created: list[SuggestionMaster] = []
        for c in items:
            code = c["underlyingCode"]
            m = SuggestionMaster(
                tradeDate=today, sessionNo=await master_repo.next_session_no(session, today, code),
                underlyingCode=code, underlyingType=c["underlyingType"], state="RUNNING", params=params,
                researchRunId=sel["runId"], researchScore=c.get("opportunityScore") or c.get("score"),
                direction=(c.get("direction") or "").upper() or None, newsStatus=c.get("newsStatus"),
                inResearch=not c.get("_missing", False), startedAt=now,
                lastNote=None if not c.get("_missing") else "Not in the latest Research run",
            )
            created.append(await master_repo.save(session, m))
        await session.commit()
        return {"started": True, "masters": [self.master_dict(m) for m in created]}

    async def stop(self, session: AsyncSession, master_id: int) -> dict[str, Any]:
        m = await master_repo.get(session, master_id)
        if m is None:
            raise NotFoundException(f"Suggestion master {master_id} not found")
        if m.state == "RUNNING":
            m.state, m.stopReason, m.stoppedAt = "STOPPED", "STOPPED_BY_USER", datetime.now(UTC)
            await session.commit()
        return self.master_dict(m)

    async def stop_all(self, session: AsyncSession) -> dict[str, Any]:
        now = datetime.now(UTC)
        rows = await master_repo.running(session)
        for m in rows:
            m.state, m.stopReason, m.stoppedAt = "STOPPED", "STOPPED_BY_USER", now
        await session.commit()
        return {"stopped": len(rows), "masters": [self.master_dict(m) for m in rows]}

    # ───────────────────────── one iteration ─────────────────────────
    async def iterate(self, master_id: int) -> dict[str, Any]:
        lock = self._locks.setdefault(master_id, asyncio.Lock())
        if lock.locked():
            raise ConflictException("This card is already iterating", error={"code": "ITERATION_IN_PROGRESS"})
        async with lock:
            return await self._iterate(master_id)

    async def _iterate(self, master_id: int) -> dict[str, Any]:
        t0, now = time.monotonic(), datetime.now(UTC)
        async with async_session_factory() as s:
            m = await master_repo.get(s, master_id)
            if m is None:
                raise NotFoundException(f"Suggestion master {master_id} not found")
            if m.state == "RUNNING" and m.tradeDate != _today():
                m.state, m.stopReason, m.stoppedAt = "STOPPED", "DAY_ENDED", now
                await s.commit()
            if m.state != "RUNNING":
                return {"master": self.master_dict(m), "ran": False, "saved": 0}
            m.lastStartedAt = now
            code, params, iteration = m.underlyingCode, dict(m.params or {}), m.iterationsCompleted + 1
            sel = await select_underlyings(s, ALL_IN_RESEARCH, ALL_IN_RESEARCH, [code])
            research = sel["items"][0] if sel["items"] else None
            await s.commit()

        picks: list[dict[str, Any]] = []
        prices: dict[str, float] = {}
        note, error = "", None
        try:
            if research is None:
                note = "Not in the latest Research run -- nothing to analyse until Research covers it again"
            else:
                out = await underlying_graph.ainvoke(
                    {"masterId": master_id, "params": params, "research": research, "code": code}
                )
                note = out.get("error") or out.get("note") or ""
                ranked = sorted(out.get("candidates", []), key=lambda c: (c.get("edge", 0), c["confidence"]),
                                reverse=True)
                picks = ranked[: params.get("maxPerUnderlying", 2)]
                for i, c in enumerate(picks, 1):
                    c["rank"] = i
                for ch in (out.get("market") or {}).get("chains", []):
                    for row in ch["strikes"]:
                        for side in ("CE", "PE"):
                            if row[side]["key"]:
                                prices[row[side]["key"]] = row[side]["ltp"]
        except Exception as e:  # one bad iteration must not kill the card
            logger.error(f"suggestion iterate master={master_id} {code} failed: {type(e).__name__}: {e}")
            error = f"{type(e).__name__}: {e}"

        async with async_session_factory() as s:
            m = await master_repo.get(s, master_id)
            assert m is not None
            saved = 0
            if error is None:
                saved = await self._save(s, m, iteration, picks, params)
                await memory_service.resolve_outcomes(s, prices)
                m.iterationsCompleted = iteration
                m.lastCompletedAt = datetime.now(UTC)
                m.lastNote, m.lastError = note or None, None
                m.lastSuggestionCount = saved
                m.suggestionsTotal += saved
                m.topConfidence = max([m.topConfidence] + [c["confidence"] for c in picks])
                m.inResearch = research is not None
                if research is not None:
                    m.researchScore = research.get("opportunityScore") or research.get("score")
                    m.direction = (research.get("direction") or "").upper() or None
                    m.newsStatus = research.get("newsStatus")
            else:
                m.iterationsFailed += 1
                m.lastError = error[:2000]
            m.lastDurationMs = int((time.monotonic() - t0) * 1000)
            await s.commit()
            return {"master": self.master_dict(m), "ran": True, "saved": saved}

    async def _save(self, s: AsyncSession, m: SuggestionMaster, iteration: int,
                    picks: list[dict[str, Any]], params: dict[str, Any]) -> int:
        """This iteration's picks become the card's 'latest' set (an empty set clears the old one)."""
        now = datetime.now(UTC)
        valid_until = now + timedelta(minutes=params.get("validMinutes", 15))
        rows = [
            TradeSuggestion(
                masterId=m.id, iterationNo=iteration, ref=make_ref(m.underlyingCode, m, iteration, c["rank"]),
                underlyingCode=m.underlyingCode, underlyingType=m.underlyingType, contractId=c["id"],
                instrumentKey=c.get("instrumentKey"), optionType=c["side"], spot=c.get("spot", 0),
                strike=c["strike"], expiry=c["expiry"], entry=c["entry"], stop=c["stop"], target=c["target"],
                profitMarginPct=c["marginPct"], rewardRisk=c["rewardRisk"], confidence=c["confidence"],
                riskLevel=risk_level(c["confidence"], c["rewardRisk"], c.get("spreadPct", 0)), rank=c["rank"],
                strategy=c.get("strategy"), reasons=c.get("reasons", []), risks=c.get("risks", []),
                source=c["source"], validUntil=valid_until, isLatest=True,
            )
            for c in picks
        ]
        await suggestion_repository.replace_latest(s, m.underlyingCode, rows)
        for row, c in zip(rows, picks, strict=True):
            await memory_service.remember_pending(s, row, c.get("bias", "NEUTRAL"), "UNKNOWN")
        return len(rows)

    # ───────────────────────── reads ─────────────────────────
    async def research_top(self, session: AsyncSession) -> dict[str, Any]:
        """API 1 for the page: best underlyings from the Research Engine (top 5 INDEX + top 3 COMMODITY)."""
        sel = await select_underlyings(session, 5, 3)
        return {
            "hasResearch": sel["runId"] is not None,
            "researchRunId": sel["runId"],
            "list": [
                {
                    "code": c["underlyingCode"],
                    "type": c["underlyingType"],
                    "direction": (c.get("direction") or "").upper() or None,
                    "newsStatus": c.get("newsStatus"),
                    "score": c.get("opportunityScore") or c.get("score"),
                }
                for c in sel["items"]
            ],
        }

    async def today(self, session: AsyncSession) -> dict[str, Any]:
        """
        API 2 for the page: today's newest session (master) per underlying, with its live suggestion
        counts. The page merges this with research_top(): a card with a master shows the master,
        a card without one shows the Research item and a Start button.
        """
        today = _today()
        if await master_repo.close_stale_days(session, today, datetime.now(UTC)):
            await session.commit()
        masters = await master_repo.latest_for_day(session, today)
        latest = await suggestion_repository.latest(session, list(masters)) if masters else []
        now = datetime.now(UTC)
        stats: dict[str, dict[str, int]] = {}
        for sg in latest:
            if sg.validUntil < now:
                continue
            d = stats.setdefault(sg.underlyingCode, {"count": 0, "top": 0, "ce": 0, "pe": 0})
            d["count"] += 1
            d["ce" if sg.optionType == "CE" else "pe"] += 1
            d["top"] = max(d["top"], sg.confidence)
        items = []
        for code, m in masters.items():
            st = stats.get(code, {})
            items.append({
                **self.master_dict(m),
                "liveCount": st.get("count", 0), "callCount": st.get("ce", 0), "putCount": st.get("pe", 0),
                "liveTopConfidence": st.get("top", 0),
            })
        return {"tradeDate": today, "list": items}

    async def latest(self, session: AsyncSession, code: str | None = None) -> dict[str, Any]:
        rows = await suggestion_repository.latest(session, [code] if code else None)
        now = datetime.now(UTC)
        items = [self.to_dict(r, now) for r in rows]
        return {"list": items, "generatedAt": max((i["createdAt"] for i in items), default=None)}

    @staticmethod
    def _missing(code: str) -> dict[str, Any]:
        cfg = get_config(code)
        return {"underlyingCode": code, "underlyingType": cfg.type if cfg else "INDEX", "_missing": True}

    @staticmethod
    def master_dict(m: SuggestionMaster) -> dict[str, Any]:
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {
            "id": m.id, "tradeDate": m.tradeDate, "sessionNo": m.sessionNo, "underlyingCode": m.underlyingCode,
            "underlyingType": m.underlyingType, "state": m.state, "stopReason": m.stopReason,
            "params": m.params, "researchRunId": m.researchRunId,
            "researchScore": float(m.researchScore) if m.researchScore is not None else None,
            "direction": m.direction, "newsStatus": m.newsStatus, "inResearch": m.inResearch,
            "iterationsCompleted": m.iterationsCompleted, "iterationsFailed": m.iterationsFailed,
            "suggestionsTotal": m.suggestionsTotal, "lastSuggestionCount": m.lastSuggestionCount,
            "topConfidence": m.topConfidence, "lastNote": m.lastNote, "lastError": m.lastError,
            "lastDurationMs": m.lastDurationMs, "startedAt": iso(m.startedAt), "lastStartedAt": iso(m.lastStartedAt),
            "lastCompletedAt": iso(m.lastCompletedAt), "stoppedAt": iso(m.stoppedAt),
            "createdAt": iso(m.createdAt),
        }

    @staticmethod
    def to_dict(s: TradeSuggestion, now: datetime) -> dict[str, Any]:
        return {
            "id": s.id, "ref": s.ref, "masterId": s.masterId, "iterationNo": s.iterationNo, "spot": float(s.spot),
            "riskLevel": s.riskLevel, "underlyingCode": s.underlyingCode, "underlyingType": s.underlyingType,
            "contractId": s.contractId, "optionType": s.optionType, "strike": float(s.strike), "expiry": s.expiry,
            "entry": float(s.entry), "stop": float(s.stop), "target": float(s.target),
            "profitMarginPct": float(s.profitMarginPct), "rewardRisk": float(s.rewardRisk),
            "confidence": s.confidence, "rank": s.rank, "strategy": s.strategy, "reasons": s.reasons,
            "risks": s.risks, "source": s.source, "validUntil": s.validUntil.isoformat(),
            "ageSeconds": int((now - s.createdAt).total_seconds()),
            "expired": s.validUntil < now, "outcome": s.outcome, "isLatest": s.isLatest,
            "createdAt": s.createdAt.isoformat(),
        }


suggestion_run_service = SuggestionRunService()
