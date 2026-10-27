from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suggestion.entity.suggestion_entity import SUGGESTION_ENTITIES


def entity_for(code: str) -> Any:
    ent = SUGGESTION_ENTITIES.get(code.upper())
    if ent is None:
        raise KeyError(f"No suggestion table for {code}")
    return ent


class SuggestionRepository:
    """Reads and writes the per-underlying suggestion tables."""

    async def replace_latest(self, session: AsyncSession, code: str, rows: list[Any]) -> None:
        ent = entity_for(code)
        await session.execute(update(ent).where(ent.isLatest.is_(True)).values(isLatest=False))
        for r in rows:
            session.add(r)
        await session.flush()

    async def latest(self, session: AsyncSession, codes: Iterable[str] | None = None) -> list[Any]:
        out: list[Any] = []
        for code in codes or SUGGESTION_ENTITIES.keys():
            ent = entity_for(code)
            res = await session.execute(
                select(ent).where(ent.status == 1).where(ent.isLatest.is_(True)).order_by(ent.rank.asc())
            )
            out.extend(res.scalars().all())
        return out

    async def history(self, session: AsyncSession, code: str, limit: int = 50) -> list[Any]:
        ent = entity_for(code)
        res = await session.execute(
            select(ent).where(ent.status == 1).order_by(ent.createdAt.desc(), ent.rank.asc()).limit(limit)
        )
        return list(res.scalars().all())

    async def pending(self, session: AsyncSession) -> list[Any]:
        out: list[Any] = []
        for code in SUGGESTION_ENTITIES:
            ent = entity_for(code)
            res = await session.execute(select(ent).where(ent.status == 1).where(ent.outcome == "PENDING"))
            out.extend(res.scalars().all())
        return out


def make_ref(code: str, run_id: int, rank: int, now: datetime) -> str:
    """Readable id such as SG-NIFTY-20261027-0013-01."""
    return f"SG-{code}-{now:%Y%m%d}-{run_id:04d}-{rank:02d}"


def risk_level(confidence: int, reward_risk: float, spread_pct: float) -> str:
    if confidence >= 80 and reward_risk >= 2 and spread_pct <= 2:
        return "LOW"
    if confidence >= 70 and reward_risk >= 1.5:
        return "MEDIUM"
    return "HIGH"


suggestion_repository = SuggestionRepository()
