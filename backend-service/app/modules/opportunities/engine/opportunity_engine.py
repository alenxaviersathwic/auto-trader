from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.opportunities.entity.opportunity_entity import OpportunityMaster
from app.modules.opportunities.schema.opportunity_schema import StartOpportunityRequest
from app.modules.opportunities.service.run_service import opportunity_run_service as svc
from app.modules.system.service.engine_registry import Engine, engine_registry


class OpportunityEngine(Engine):
    """Opportunities Engine registered in the System Status engine registry."""

    code: str = "opportunities"
    name: str = "Opportunities"
    description: str = (
        "One session per Research card per Start; the Opportunities page iterates each card one by one"
    )
    module: str = "opportunities"
    runnable: bool = True
    paramSchema: dict[str, Any] = StartOpportunityRequest.model_json_schema()

    async def start(self, params: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
        """Creates today's card sessions. Iterations run while the Opportunities page is open."""
        valid = {k: v for k, v in params.items() if k in StartOpportunityRequest.model_fields}
        return await svc.start(StartOpportunityRequest(**valid), session)

    async def cancel(self, session: AsyncSession) -> dict[str, Any]:
        return await svc.stop_all(session)

    async def current_state(self, session: AsyncSession) -> dict[str, Any]:
        masters = (await svc.today(session))["list"]
        running = [m for m in masters if m["state"] == "RUNNING"]
        return {
            "state": "RUNNING" if running else "IDLE",
            "currentNode": None,
            "progressPct": 0,
            "stats": {
                "runningCards": len(running),
                "iterationsCompleted": sum(m["iterationsCompleted"] for m in masters),
                "opportunitiesTotal": sum(m["opportunitiesTotal"] for m in masters),
            },
        }

    async def last_runs(self, n: int, session: AsyncSession) -> list[dict[str, Any]]:
        res = await session.execute(
            select(OpportunityMaster).where(OpportunityMaster.status == 1).order_by(OpportunityMaster.id.desc()).limit(n)
        )
        return [
            {"runId": m.id, "state": m.state, "startedAt": m.startedAt.isoformat() if m.startedAt else None,
             "finishedAt": (m.stoppedAt or m.lastCompletedAt).isoformat() if (m.stoppedAt or m.lastCompletedAt) else None,
             "stats": {"underlying": m.underlyingCode, "sessionNo": m.sessionNo,
                       "iterationsCompleted": m.iterationsCompleted, "opportunitiesTotal": m.opportunitiesTotal}}
            for m in res.scalars().all()
        ]


opportunity_engine = OpportunityEngine()
engine_registry.register(opportunity_engine)

