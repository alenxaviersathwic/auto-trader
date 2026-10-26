from typing import Any, Dict, List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.research.entity.research_entity import ResearchEntity, ResearchCandidate, ResearchRun
from app.modules.research.service.run_service import run_service
from app.modules.system.service.engine_registry import Engine, engine_registry


class ResearchEngine(Engine):
    """
    Research Engine implementation registered in the decoupled System Status engine registry.
    """

    code: str = "research"
    name: str = "Research"
    description: str = (
        "Reads the newest articles and suggests index and commodity underlyings with no negative news"
    )
    module: str = "research"
    runnable: bool = True
    paramSchema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["INDEX", "COMMODITY"],
            },
            "windowHours": {
                "type": "integer",
                "default": 24,
                "minimum": 6,
                "maximum": 48,
            },
            "topN": {
                "type": "integer",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
            "maxDocsPerUnderlying": {
                "type": "integer",
                "default": 20,
                "minimum": 5,
                "maximum": 50,
            },
        },
    }

    async def start(self, params: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        run_id = await run_service.start_run(
            scope=params.get("scope"),
            params=params,
            trigger_source="SYSTEM_STATUS",
            session=session,
        )
        return {"runId": run_id}

    async def cancel(self, session: AsyncSession) -> Dict[str, Any]:
        active_id = await run_service.get_active_run_id(session)
        if active_id is not None:
            await run_service.cancel_run(active_id, session)
            return {"cancelledRunId": active_id, "state": "CANCELLED"}
        return {"cancelledRunId": None, "state": "IDLE"}

    async def current_state(self, session: AsyncSession) -> Dict[str, Any]:
        # 1. Check if a run is currently active
        active_id = await run_service.get_active_run_id(session)
        if active_id is not None:
            run_res = await session.execute(
                select(ResearchRun).where(ResearchRun.id == active_id)
            )
            run = run_res.scalar_one_or_none()
            return {
                "state": run.state if run else "RUNNING",
                "currentNode": run.currentNode if run else None,
                "progressPct": run.progressPct if run else 0,
                "stats": run.stats if run else {},
            }

        # 2. Get last finished run
        last_res = await session.execute(
            select(ResearchRun)
            .where(ResearchRun.status == 1)
            .where(ResearchRun.state.in_(["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"]))
            .order_by(ResearchRun.id.desc())
            .limit(1)
        )
        last_run = last_res.scalar_one_or_none()

        last_summary = None
        last_at = None
        stats = {}
        if last_run:
            last_at = last_run.finishedAt.isoformat() if last_run.finishedAt else last_run.createdAt.isoformat()
            stats = last_run.stats or {}

            # Construct summary per underlying type
            cands_res = await session.execute(
                select(ResearchCandidate)
                .where(ResearchCandidate.runId == last_run.id)
                .where(ResearchCandidate.status == 1)
            )
            cands = cands_res.scalars().all()
            if cands:
                index_cands = [c for c in cands if c.underlyingType == "INDEX"]
                comm_cands = [c for c in cands if c.underlyingType == "COMMODITY"]

                idx_sugg = sum(1 for c in index_cands if c.suggested)
                idx_neg = sum(1 for c in index_cands if c.newsStatus == "HAS_NEGATIVE")
                idx_no = sum(1 for c in index_cands if c.newsStatus == "NO_COVERAGE")

                comm_sugg = sum(1 for c in comm_cands if c.suggested)
                comm_neg = sum(1 for c in comm_cands if c.newsStatus == "HAS_NEGATIVE")

                parts = []
                if index_cands:
                    parts.append(f"INDEX: {idx_sugg} suggested, {idx_neg} has negative news, {idx_no} no coverage")
                if comm_cands:
                    parts.append(f"COMMODITY: {comm_sugg} suggested, {comm_neg} has negative news")
                last_summary = " · ".join(parts)
            else:
                last_summary = f"{last_run.state}: {last_run.resultKind or 'No candidates'}"

        # 3. Aggregate monitored underlyings count
        cand_count_res = await session.execute(
            select(func.count(ResearchEntity.id)).where(ResearchEntity.status == 1)
        )
        cand_count = cand_count_res.scalar() or 0
        stored_info = f"{cand_count} underlyings monitored"

        return {
            "state": "IDLE",
            "lastRunSummary": last_summary,
            "lastRunAt": last_at,
            "storedInfo": stored_info,
            "stats": stats,
        }

    async def last_runs(self, n: int, session: AsyncSession) -> List[Dict[str, Any]]:
        res = await session.execute(
            select(ResearchRun)
            .where(ResearchRun.status == 1)
            .order_by(ResearchRun.id.desc())
            .limit(n)
        )
        runs = res.scalars().all()
        return [
            {
                "id": r.id,
                "scope": r.scope,
                "state": r.state,
                "resultKind": r.resultKind,
                "startedAt": r.startedAt.isoformat() if r.startedAt else None,
                "finishedAt": r.finishedAt.isoformat() if r.finishedAt else None,
                "stats": r.stats,
                "error": r.error,
            }
            for r in runs
        ]


# Instantiate and register into EngineRegistry
research_engine = ResearchEngine()
engine_registry.register(research_engine)
