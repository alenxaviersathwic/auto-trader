from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.opportunities.entity.opportunity_entity import OpportunityMemory
from app.modules.opportunities.repository.opportunity_repository import opportunity_repository
from app.modules.research.llm.embedding_client import embedding_client

MAX_MEMORY_PER_UNDERLYING = 200


async def recall(session: AsyncSession, code: str, bias: str, brief_text: str, k: int = 3) -> list[str]:
    """Resolved cases only (pending is never shown). Filter first, then similarity."""
    vec = await embedding_client.get_embedding(brief_text)
    res = await session.execute(
        select(OpportunityMemory)
        .where(OpportunityMemory.status == 1)
        .where(OpportunityMemory.underlyingCode == code)
        .where(OpportunityMemory.direction == bias)
        .where(OpportunityMemory.outcome.in_(["TARGET_HIT", "STOP_HIT", "EXPIRED"]))
        .order_by(OpportunityMemory.embedding.cosine_distance(vec))
        .limit(k)
    )
    return [f"[{m.outcome}] {m.summary}" for m in res.scalars().all()]


async def remember_pending(session: AsyncSession, opp: Any, bias: str, day_type: str) -> None:
    text = (
        f"{opp.underlyingCode} {opp.optionType} {opp.strike} {opp.expiry} bias={bias} "
        f"entry={opp.entry} stop={opp.stop} target={opp.target} strategy={opp.strategy}; "
        f"reasons: {'; '.join(opp.reasons[:3])}"
    )
    session.add(
        OpportunityMemory(
            opportunityId=opp.id,
            underlyingCode=opp.underlyingCode,
            direction=bias,
            dayType=day_type,
            hourBucket=datetime.now(UTC).hour,
            summary=text[:500],
            outcome="PENDING",
            embedding=await embedding_client.get_embedding(text),
        )
    )
    await _prune(session, opp.underlyingCode)


async def _prune(session: AsyncSession, code: str) -> None:
    """Merge/prune: keep only the newest N resolved memories per underlying."""
    res = await session.execute(
        select(OpportunityMemory.id)
        .where(OpportunityMemory.underlyingCode == code)
        .where(OpportunityMemory.status == 1)
        .order_by(OpportunityMemory.id.desc())
        .offset(MAX_MEMORY_PER_UNDERLYING)
    )
    old = [r for (r,) in res.all()]
    if old:
        await session.execute(update(OpportunityMemory).where(OpportunityMemory.id.in_(old)).values(status=0))


async def sync_outcome(session: AsyncSession, opp) -> None:
    """Mirrors a trade_opportunities outcome onto its memory row. The outcome itself is decided ONLY by the
    candle checker (run_service._evaluate_opportunities); a price snapshot must never decide it."""
    await session.execute(
        update(OpportunityMemory)
        .where(OpportunityMemory.opportunityId == opp.id)
        .where(OpportunityMemory.underlyingCode == opp.underlyingCode).values(outcome=opp.outcome)
    )


async def hit_rate(session: AsyncSession, code: str, last_n: int = 100) -> str:
    """How often past opportunities for this underlying hit target before stop (resolved ones only)."""
    res = await session.execute(
        select(OpportunityMemory.outcome)
        .where(OpportunityMemory.status == 1)
        .where(OpportunityMemory.underlyingCode == code)
        .where(OpportunityMemory.outcome.in_(["TARGET_HIT", "STOP_HIT", "EXPIRED"]))
        .order_by(OpportunityMemory.id.desc())
        .limit(last_n)
    )
    outcomes = [o for (o,) in res.all()]
    if not outcomes:
        return "no history yet"
    wins = sum(1 for o in outcomes if o == "TARGET_HIT")
    return f"{wins}/{len(outcomes)} = {wins * 100 // len(outcomes)}%"

