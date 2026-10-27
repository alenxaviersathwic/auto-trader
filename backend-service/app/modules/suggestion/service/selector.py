from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.service.run_service import run_service as research_run_service
from app.modules.suggestion.provider.underlying_config import get_config


def _opportunity(c: dict[str, Any]):
    """Strongest opportunity score first (bullish = calls, bearish = puts, both count equally)."""
    return -(c.get("opportunityScore") or c.get("score") or 0)


async def select_underlyings(
    session: AsyncSession,
    index_count: int = 5,
    commodity_count: int = 3,
    only: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Top N INDEX + top M COMMODITY from the latest Research run. Returns {runId, items}."""
    chosen: list[dict[str, Any]] = []
    run_id = None
    for utype, count in (("INDEX", index_count), ("COMMODITY", commodity_count)):
        data = await research_run_service.get_latest_results(utype, session)
        if not data.get("run"):
            continue
        run_id = data["run"]["id"]
        pool = (
            data["suggested"] + data["mixed"] + data["clearNeutral"]
            + data["bearishWatch"] + data["hasNegative"]
        )
        seen, ordered = set(), []
        for c in sorted(pool, key=_opportunity):
            code = (c.get("underlyingCode") or c.get("item") or "").upper()
            if code and code not in seen and get_config(code):
                seen.add(code)
                ordered.append({**c, "underlyingCode": code, "underlyingType": utype})
        chosen += ordered[:count]
    if only is not None:
        wanted = {o.upper() for o in only}
        chosen = [c for c in chosen if c["underlyingCode"] in wanted]
    return {"runId": run_id, "items": chosen}
