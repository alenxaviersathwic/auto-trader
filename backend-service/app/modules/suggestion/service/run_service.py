import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import async_session_factory
from app.core.logging.logger import logger
from app.modules.research.service.run_service import run_service as research_run_service
from app.modules.suggestion.entity.suggestion_entity import SuggestionRun
from app.modules.suggestion.graph.builder import suggestion_graph
from app.modules.suggestion.repository.suggestion_repository import suggestion_repository
from app.modules.suggestion.schema.suggestion_schema import StartSuggestionRequest
from app.modules.suggestion.service.selector import select_underlyings


class SuggestionRunService:
    """
    Runs the Suggestion graph in a loop: when one run finishes the next one starts,
    until Stop is clicked. Single loop at a time (single uvicorn worker).
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._loop_id: str | None = None
        self._iteration = 0
        self._stop_reason: str | None = None
        self._active: set[str] = set()
        # cache: code -> {"at": ISO time the last COMPLETED loop finished, "loop": loop number}
        self._completed: dict[str, dict[str, Any]] = {}
        self._notes: dict[str, str] = {}
        self._params: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def is_looping(self) -> bool:
        return self._task is not None and not self._task.done()

    async def research_has_data(self, session: AsyncSession) -> bool:
        for utype in ("INDEX", "COMMODITY"):
            data = await research_run_service.get_latest_results(utype, session)
            if data.get("run"):
                return True
        return False

    async def start(self, req: StartSuggestionRequest, session: AsyncSession) -> dict[str, Any]:
        async with self._lock:
            # 1. Run button rule: check Research has data first
            if not await self.research_has_data(session):
                return {
                    "started": False,
                    "reason": "NO_RESEARCH_DATA",
                    "message": "Research Engine has no data yet. Run the Research Engine first.",
                }
            sel = await select_underlyings(session, req.indexCount, req.commodityCount, req.underlyings)
            codes = {c["underlyingCode"] for c in sel["items"]}
            if not codes:
                return {"started": False, "reason": "NO_UNDERLYINGS",
                        "message": "No matching underlyings in Research."}
            self._active |= codes
            self._stop_reason = None
            if self.is_looping:  # card Run while the loop is going: just join it
                return {"started": True, "loopId": self._loop_id, "active": sorted(self._active)}
            self._params = req.model_dump()
            self._loop_id = uuid.uuid4().hex[:12]
            self._iteration = 0
            self._task = asyncio.create_task(self._loop(self._loop_id))
            return {"started": True, "loopId": self._loop_id, "active": sorted(self._active)}

    async def stop(self, session: AsyncSession, underlyings: list[str] | None = None) -> dict[str, Any]:
        if not self.is_looping:
            self._active.clear()
            return {"stopped": False, "state": "IDLE"}
        if underlyings:
            self._active -= {u.upper() for u in underlyings}
            if self._active:  # others keep looping; removed ones drop out from the next run
                return {"stopped": True, "state": "RUNNING", "active": sorted(self._active)}
        self._active.clear()
        self._stop_reason = "STOPPED_BY_USER"
        assert self._task is not None
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        return {"stopped": True, "state": "CANCELLED", "active": []}

    async def underlyings(self, session: AsyncSession) -> dict[str, Any]:
        """Default screen: top 5 INDEX + top 3 COMMODITY from Research, with suggestion counts."""
        sel = await select_underlyings(session, 5, 3)
        rows = await suggestion_repository.latest(session, [c["underlyingCode"] for c in sel["items"]])
        now = datetime.now(UTC)
        stats: dict[str, dict[str, int]] = {}
        for sg in rows:
            if sg.validUntil < now:
                continue
            d = stats.setdefault(sg.underlyingCode, {"count": 0, "top": 0, "ce": 0, "pe": 0})
            d["count"] += 1
            d["ce" if sg.optionType == "CE" else "pe"] += 1
            d["top"] = max(d["top"], sg.confidence)
        completed = await self._last_completed(session)
        notes = await self._last_notes(session)
        items = []
        for c in sel["items"]:
            code = c["underlyingCode"]
            dirn = (c.get("direction") or "").upper()
            items.append({
                "code": code, "type": c["underlyingType"], "direction": dirn or None,
                "newsStatus": c.get("newsStatus"), "score": c.get("score"),
                "count": stats.get(code, {}).get("count", 0),
                "callCount": stats.get(code, {}).get("ce", 0),
                "putCount": stats.get(code, {}).get("pe", 0),
                "topConfidence": stats.get(code, {}).get("top", 0),
                "active": code in self._active and self.is_looping,
                "lastIteratedAt": (completed.get(code) or {}).get("at"),
                "lastLoop": (completed.get(code) or {}).get("loop"),
                "lastNote": notes.get(code),
            })
        return {"hasResearch": sel["runId"] is not None, "list": items}

    async def _last_completed(self, session: AsyncSession) -> dict[str, dict[str, Any]]:
        """Last completed loop per underlying: the cache first, then recent run stats after a restart."""
        out = dict(self._completed)
        res = await session.execute(
            select(SuggestionRun).where(SuggestionRun.state == "COMPLETED").order_by(SuggestionRun.id.desc()).limit(30)
        )
        for r in res.scalars().all():
            for code, entry in (r.stats or {}).get("iterated", {}).items():
                if isinstance(entry, str):  # runs saved before the loop number was stored
                    entry = {"at": entry, "loop": None}
                if isinstance(entry, dict):
                    out.setdefault(code, entry)
        return out

    async def _last_notes(self, session: AsyncSession) -> dict[str, str]:
        out = dict(self._notes)
        res = await session.execute(select(SuggestionRun).order_by(SuggestionRun.id.desc()).limit(30))
        for r in res.scalars().all():
            for code, note in (r.stats or {}).get("notes", {}).items():
                if isinstance(note, str):
                    out.setdefault(code, note)
        return out

    async def _loop(self, loop_id: str) -> None:
        run_id: int | None = None
        try:
            while True:
                self._iteration += 1
                if not self._active:
                    return
                params = {**self._params, "only": sorted(self._active)}
                async with async_session_factory() as s:
                    run = SuggestionRun(loopId=loop_id, iteration=self._iteration, state="RUNNING", params=params,
                                        startedAt=datetime.now(UTC), progressPct=1)
                    s.add(run)
                    await s.commit()
                    run_id = run.id
                final: dict[str, Any] = {}
                try:
                    final = await suggestion_graph.ainvoke({"runId": run_id, "params": params, "results": [],
                                                            "skipped": [], "prices": {}})
                    status = final.get("status", "OK")
                    await self._finish(run_id, "COMPLETED" if status == "OK" else "FAILED", final, status)
                    if status != "OK":
                        self._stop_reason = status  # e.g. NO_RESEARCH: nothing to loop on
                        return
                except asyncio.CancelledError:
                    await self._finish(run_id, "CANCELLED", final, None)
                    raise
                except Exception as e:  # one bad run must not kill the loop
                    logger.error(f"suggestion run {run_id} failed: {e}")
                    await self._finish(run_id, "FAILED", final, str(e))
                await asyncio.sleep(params.get("loopGapSeconds", 20))
        except asyncio.CancelledError:
            raise

    async def _finish(self, run_id: int, state: str, final: dict[str, Any], error: str | None) -> None:
        async with async_session_factory() as s:
            run = (await s.execute(select(SuggestionRun).where(SuggestionRun.id == run_id))).scalar_one()
            run.state, run.finishedAt, run.progressPct = state, datetime.now(UTC), 100 if state == "COMPLETED" else run.progressPct
            run.error = error if state == "FAILED" else None
            run.researchRunId = final.get("researchRunId")
            done = state == "COMPLETED"
            entry = {"at": run.finishedAt.isoformat(), "loop": run.iteration}
            completed = {code: entry for code in final.get("iterated", {})} if done else {}
            run.stats = {
                "underlyings": len(final.get("underlyings", [])),
                "candidates": len(final.get("results", [])),
                "picked": len(final.get("picks", [])),
                "aiUsed": final.get("aiUsed", 0),
                "baselineUsed": final.get("baselineUsed", 0),
                "outcomesResolved": final.get("outcomesResolved", 0),
                "skipped": final.get("skipped", []),
                "iterated": completed,
                "notes": final.get("notes", {}) if done else {},
            }
            if done:  # only a fully completed loop updates the "last completed" cache
                self._completed.update(completed)
                self._notes.update(final.get("notes", {}))
            await s.commit()

    async def status(self, session: AsyncSession) -> dict[str, Any]:
        res = await session.execute(select(SuggestionRun).order_by(SuggestionRun.id.desc()).limit(1))
        r = res.scalar_one_or_none()
        has_research = await self.research_has_data(session)
        return {
            "isLooping": self.is_looping,
            "loopId": self._loop_id,
            "iteration": self._iteration,
            "active": sorted(self._active) if self.is_looping else [],
            "stopReason": self._stop_reason,
            "researchHasData": has_research,
            "state": (r.state if r else "IDLE") if self.is_looping or r else "IDLE",
            "currentNode": r.currentNode if r and self.is_looping else None,
            "progressPct": r.progressPct if r else 0,
            "startedAt": r.startedAt.isoformat() if r and r.startedAt else None,
            "finishedAt": r.finishedAt.isoformat() if r and r.finishedAt else None,
            "stats": r.stats if r else {},
            "error": r.error if r else None,
        }

    async def latest(self, session: AsyncSession, code: str | None = None) -> dict[str, Any]:
        rows = await suggestion_repository.latest(session, [code] if code else None)
        now = datetime.now(UTC)
        items = [self.to_dict(r, now) for r in rows]
        return {"list": items, "generatedAt": max((i["createdAt"] for i in items), default=None)}

    @staticmethod
    def to_dict(s: Any, now: datetime) -> dict[str, Any]:
        return {
            "id": s.id, "ref": s.ref, "runId": s.runId, "spot": float(s.spot), "riskLevel": s.riskLevel, "underlyingCode": s.underlyingCode, "underlyingType": s.underlyingType,
            "contractId": s.contractId, "optionType": s.optionType, "strike": float(s.strike), "expiry": s.expiry,
            "entry": float(s.entry), "stop": float(s.stop), "target": float(s.target),
            "profitMarginPct": float(s.profitMarginPct), "rewardRisk": float(s.rewardRisk),
            "confidence": s.confidence, "rank": s.rank, "strategy": s.strategy, "reasons": s.reasons,
            "risks": s.risks, "source": s.source, "validUntil": s.validUntil.isoformat(),
            "ageSeconds": int((now - s.createdAt).total_seconds()),
            "expired": s.validUntil < now, "outcome": s.outcome, "createdAt": s.createdAt.isoformat(),
        }


suggestion_run_service = SuggestionRunService()
