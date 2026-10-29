from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suggestion.entity.suggestion_entity import SuggestionMaster, TradeSuggestion


class SuggestionRepository:
    """Reads and writes trade_suggestions (one table for every underlying)."""

    async def replace_latest(self, session: AsyncSession, code: str, rows: list[TradeSuggestion]) -> None:
        """New iteration for an underlying: its previous 'latest' set stops being latest."""
        await session.execute(
            update(TradeSuggestion)
            .where(TradeSuggestion.underlyingCode == code)
            .where(TradeSuggestion.isLatest.is_(True))
            .values(isLatest=False)
        )
        for r in rows:
            session.add(r)
        await session.flush()

    async def latest(self, session: AsyncSession, codes: Iterable[str] | None = None) -> list[TradeSuggestion]:
        q = (
            select(TradeSuggestion)
            .where(TradeSuggestion.status == 1)
            .where(TradeSuggestion.isLatest.is_(True))
            .order_by(TradeSuggestion.underlyingCode, TradeSuggestion.rank.asc())
        )
        if codes is not None:
            q = q.where(TradeSuggestion.underlyingCode.in_([c.upper() for c in codes]))
        return list((await session.execute(q)).scalars().all())

    async def pending(self, session: AsyncSession) -> list[TradeSuggestion]:
        res = await session.execute(
            select(TradeSuggestion).where(TradeSuggestion.status == 1).where(TradeSuggestion.outcome == "PENDING")
        )
        return list(res.scalars().all())


class SuggestionMasterRepository:
    """Reads and writes suggestion_masters (one row per card per Start)."""

    async def get(self, session: AsyncSession, master_id: int) -> SuggestionMaster | None:
        res = await session.execute(
            select(SuggestionMaster).where(SuggestionMaster.id == master_id).where(SuggestionMaster.status == 1)
        )
        return res.scalar_one_or_none()

    async def save(self, session: AsyncSession, m: SuggestionMaster) -> SuggestionMaster:
        session.add(m)
        await session.flush()
        return m

    async def next_session_no(self, session: AsyncSession, trade_date: str, code: str) -> int:
        res = await session.execute(
            select(func.coalesce(func.max(SuggestionMaster.sessionNo), 0))
            .where(SuggestionMaster.tradeDate == trade_date)
            .where(SuggestionMaster.underlyingCode == code)
            .where(SuggestionMaster.status == 1)
        )
        return int(res.scalar_one()) + 1

    async def running(
        self, session: AsyncSession, trade_date: str | None = None, codes: Iterable[str] | None = None
    ) -> list[SuggestionMaster]:
        q = select(SuggestionMaster).where(SuggestionMaster.status == 1).where(SuggestionMaster.state == "RUNNING")
        if trade_date:
            q = q.where(SuggestionMaster.tradeDate == trade_date)
        if codes is not None:
            q = q.where(SuggestionMaster.underlyingCode.in_([c.upper() for c in codes]))
        return list((await session.execute(q.order_by(SuggestionMaster.id))).scalars().all())

    async def latest_for_day(self, session: AsyncSession, trade_date: str) -> dict[str, SuggestionMaster]:
        """The newest master (highest sessionNo) of each underlying for that day."""
        res = await session.execute(
            select(SuggestionMaster)
            .where(SuggestionMaster.status == 1)
            .where(SuggestionMaster.tradeDate == trade_date)
            .order_by(SuggestionMaster.underlyingCode, SuggestionMaster.sessionNo.desc())
        )
        out: dict[str, SuggestionMaster] = {}
        for m in res.scalars().all():
            out.setdefault(m.underlyingCode, m)
        return out

    async def close_stale_days(self, session: AsyncSession, today: str, now: datetime) -> int:
        """Masters still RUNNING from an earlier day are stopped: a session never crosses midnight."""
        res = await session.execute(
            update(SuggestionMaster)
            .where(SuggestionMaster.state == "RUNNING")
            .where(SuggestionMaster.tradeDate < today)
            .values(state="STOPPED", stopReason="DAY_ENDED", stoppedAt=now)
        )
        return res.rowcount or 0


def make_ref(code: str, master: SuggestionMaster, iteration: int, rank: int) -> str:
    """Readable id such as SG-NIFTY-20261029-S01-I0005-01 (day, session, iteration, rank)."""
    return f"SG-{code}-{master.tradeDate.replace('-', '')}-S{master.sessionNo:02d}-I{iteration:04d}-{rank:02d}"


def risk_level(confidence: int, reward_risk: float, spread_pct: float) -> str:
    if confidence >= 80 and reward_risk >= 2 and spread_pct <= 2:
        return "LOW"
    if confidence >= 70 and reward_risk >= 1.5:
        return "MEDIUM"
    return "HIGH"


suggestion_repository = SuggestionRepository()
suggestion_master_repository = SuggestionMasterRepository()
