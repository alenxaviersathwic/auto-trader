from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.research.llm.embedding_client import embedding_client
from app.modules.suggestion.entity.suggestion_entity import SuggestionMemory
from app.modules.suggestion.repository.suggestion_repository import suggestion_repository

MAX_MEMORY_PER_UNDERLYING = 200


async def recall(session: AsyncSession, code: str, bias: str, brief_text: str, k: int = 3) -> list[str]:
    """Resolved cases only (pending is never shown). Filter first, then similarity."""
    vec = await embedding_client.get_embedding(brief_text)
    res = await session.execute(
        select(SuggestionMemory)
        .where(SuggestionMemory.status == 1)
        .where(SuggestionMemory.underlyingCode == code)
        .where(SuggestionMemory.direction == bias)
        .where(SuggestionMemory.outcome.in_(["TARGET_HIT", "STOP_HIT", "EXPIRED"]))
        .order_by(SuggestionMemory.embedding.cosine_distance(vec))
        .limit(k)
    )
    return [f"[{m.outcome}] {m.summary}" for m in res.scalars().all()]


async def remember_pending(session: AsyncSession, sug: Any, bias: str, day_type: str) -> None:
    text = (
        f"{sug.underlyingCode} {sug.optionType} {sug.strike} {sug.expiry} bias={bias} "
        f"entry={sug.entry} stop={sug.stop} target={sug.target} strategy={sug.strategy}; "
        f"reasons: {'; '.join(sug.reasons[:3])}"
    )
    session.add(
        SuggestionMemory(
            suggestionId=sug.id,
            underlyingCode=sug.underlyingCode,
            direction=bias,
            dayType=day_type,
            hourBucket=datetime.now(UTC).hour,
            summary=text[:500],
            outcome="PENDING",
            embedding=await embedding_client.get_embedding(text),
        )
    )
    await _prune(session, sug.underlyingCode)


async def _prune(session: AsyncSession, code: str) -> None:
    """Merge/prune: keep only the newest N resolved memories per underlying."""
    res = await session.execute(
        select(SuggestionMemory.id)
        .where(SuggestionMemory.underlyingCode == code)
        .where(SuggestionMemory.status == 1)
        .order_by(SuggestionMemory.id.desc())
        .offset(MAX_MEMORY_PER_UNDERLYING)
    )
    old = [r for (r,) in res.all()]
    if old:
        await session.execute(update(SuggestionMemory).where(SuggestionMemory.id.in_(old)).values(status=0))


async def resolve_outcomes(session: AsyncSession, prices: dict[str, float]) -> int:
    """Marks TARGET_HIT / STOP_HIT / EXPIRED from latest prices and updates the memory."""
    now = datetime.now(UTC)
    pending = await suggestion_repository.pending(session)
    changed = 0
    for s in pending:
        ltp = prices.get(s.instrumentKey or "")
        outcome = None
        if ltp is not None and ltp >= float(s.target):
            outcome = "TARGET_HIT"
        elif ltp is not None and ltp <= float(s.stop):
            outcome = "STOP_HIT"
        elif s.validUntil < now:
            outcome = "EXPIRED"
        if outcome:
            s.outcome, s.resolvedAt = outcome, now
            await session.execute(
                update(SuggestionMemory)
                .where(SuggestionMemory.suggestionId == s.id)
                .where(SuggestionMemory.underlyingCode == s.underlyingCode).values(outcome=outcome)
            )
            changed += 1
    return changed


async def hit_rate(session: AsyncSession, code: str, last_n: int = 100) -> str:
    """How often past suggestions for this underlying hit target before stop (resolved ones only)."""
    res = await session.execute(
        select(SuggestionMemory.outcome)
        .where(SuggestionMemory.status == 1)
        .where(SuggestionMemory.underlyingCode == code)
        .where(SuggestionMemory.outcome.in_(["TARGET_HIT", "STOP_HIT", "EXPIRED"]))
        .order_by(SuggestionMemory.id.desc())
        .limit(last_n)
    )
    outcomes = [o for (o,) in res.all()]
    if not outcomes:
        return "no history yet"
    wins = sum(1 for o in outcomes if o == "TARGET_HIT")
    return f"{wins}/{len(outcomes)} = {wins * 100 // len(outcomes)}%"
