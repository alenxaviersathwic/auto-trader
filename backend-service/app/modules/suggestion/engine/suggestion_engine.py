from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suggestion.entity.suggestion_entity import SuggestionRun
from app.modules.suggestion.schema.suggestion_schema import StartSuggestionRequest
from app.modules.suggestion.service.run_service import suggestion_run_service as svc
from app.modules.system.service.engine_registry import Engine, engine_registry


class SuggestionEngine(Engine):
    """Suggestion Engine registered in the System Status engine registry."""

    code: str = "suggestion"
    name: str = "Suggestion"
    description: str = "Loops over the top Research underlyings and suggests executable option contracts"
    module: str = "suggestion"
    runnable: bool = True
    paramSchema: dict[str, Any] = StartSuggestionRequest.model_json_schema()

    async def start(self, params: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
        valid = {k: v for k, v in params.items() if k in StartSuggestionRequest.model_fields}
        return await svc.start(StartSuggestionRequest(**valid), session)

    async def cancel(self, session: AsyncSession) -> dict[str, Any]:
        return await svc.stop(session)

    async def current_state(self, session: AsyncSession) -> dict[str, Any]:
        st = await svc.status(session)
        return {"state": "RUNNING" if st["isLooping"] else "IDLE", "currentNode": st["currentNode"],
                "progressPct": st["progressPct"], "stats": st["stats"]}

    async def last_runs(self, n: int, session: AsyncSession) -> list[dict[str, Any]]:
        res = await session.execute(select(SuggestionRun).order_by(SuggestionRun.id.desc()).limit(n))
        return [{"runId": r.id, "state": r.state, "startedAt": r.startedAt.isoformat() if r.startedAt else None,
                 "finishedAt": r.finishedAt.isoformat() if r.finishedAt else None, "stats": r.stats}
                for r in res.scalars().all()]


suggestion_engine = SuggestionEngine()
engine_registry.register(suggestion_engine)
