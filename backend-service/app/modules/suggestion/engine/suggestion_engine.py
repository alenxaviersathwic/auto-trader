from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suggestion.entity.suggestion_entity import SuggestionMaster
from app.modules.suggestion.schema.suggestion_schema import StartSuggestionRequest
from app.modules.suggestion.service.run_service import suggestion_run_service as svc
from app.modules.system.service.engine_registry import Engine, engine_registry


class SuggestionEngine(Engine):
    """Suggestion Engine registered in the System Status engine registry."""

    code: str = "suggestion"
    name: str = "Suggestion"
    description: str = (
        "One session per Research card per Start; the Suggestion page iterates each card one by one"
    )
    module: str = "suggestion"
    runnable: bool = True
    paramSchema: dict[str, Any] = StartSuggestionRequest.model_json_schema()

    async def start(self, params: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
        """Creates today's card sessions. Iterations run while the Suggestion page is open."""
        valid = {k: v for k, v in params.items() if k in StartSuggestionRequest.model_fields}
        return await svc.start(StartSuggestionRequest(**valid), session)

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
                "suggestionsTotal": sum(m["suggestionsTotal"] for m in masters),
            },
        }

    async def last_runs(self, n: int, session: AsyncSession) -> list[dict[str, Any]]:
        res = await session.execute(
            select(SuggestionMaster).where(SuggestionMaster.status == 1).order_by(SuggestionMaster.id.desc()).limit(n)
        )
        return [
            {"runId": m.id, "state": m.state, "startedAt": m.startedAt.isoformat() if m.startedAt else None,
             "finishedAt": (m.stoppedAt or m.lastCompletedAt).isoformat() if (m.stoppedAt or m.lastCompletedAt) else None,
             "stats": {"underlying": m.underlyingCode, "sessionNo": m.sessionNo,
                       "iterationsCompleted": m.iterationsCompleted, "suggestionsTotal": m.suggestionsTotal}}
            for m in res.scalars().all()
        ]


suggestion_engine = SuggestionEngine()
engine_registry.register(suggestion_engine)
