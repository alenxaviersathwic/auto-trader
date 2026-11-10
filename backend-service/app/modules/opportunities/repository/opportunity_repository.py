from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.opportunities.entity.opportunity_entity import OpportunityIteration, OpportunityMaster, TradeOpportunity


class OpportunityRepository:
    """Reads and writes trade_opportunities (one table for every underlying)."""

    async def recent_contracts(
        self, session: AsyncSession, code: str, since: datetime
    ) -> dict[str, TradeOpportunity]:
        """Newest row per contract id created at/after `since` (any outcome) -- used to skip repeat signals."""
        res = await session.execute(
            select(TradeOpportunity)
            .where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.underlyingCode == code)
            .where(TradeOpportunity.createdAt >= since)
            .order_by(TradeOpportunity.id.asc())
        )
        return {r.contractId: r for r in res.scalars().all()}

    async def created_since(self, session: AsyncSession, code: str, since: datetime) -> list[TradeOpportunity]:
        """Every row of an underlying created at/after `since` (oldest first) -- the guardrails' view of today."""
        res = await session.execute(
            select(TradeOpportunity)
            .where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.underlyingCode == code)
            .where(TradeOpportunity.createdAt >= since)
            .order_by(TradeOpportunity.id.asc())
        )
        return list(res.scalars().all())

    async def resolved_recent(self, session: AsyncSession, code: str, since: datetime, limit: int = 200) -> list[TradeOpportunity]:
        """This underlying's resolved (non-PENDING) rows since `since`, oldest first -- guardrails.apply()'s
        `recent` arg for the per-setup rolling-demotion check. `limit` caps a pathological lookback window;
        guardrails._demoted_setups() only looks at the last SETUP_DEMOTE_LOOKBACK per (setup, side) anyway, so
        a generous limit here just needs to cover every setup's trades, not be exact."""
        res = await session.execute(
            select(TradeOpportunity)
            .where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.underlyingCode == code)
            .where(TradeOpportunity.outcome != "PENDING")
            .where(TradeOpportunity.resolvedAt >= since)
            .order_by(TradeOpportunity.resolvedAt.asc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def replace_latest(
        self, session: AsyncSession, code: str, rows: list[TradeOpportunity], keep_ids: Iterable[int] = ()
    ) -> None:
        """New iteration for an underlying: its previous 'latest' set stops being latest, except `keep_ids`
        (still-live rows this iteration re-signalled, which stay latest instead of being duplicated)."""
        q = (
            update(TradeOpportunity)
            .where(TradeOpportunity.underlyingCode == code)
            .where(TradeOpportunity.isLatest.is_(True))
        )
        keep = list(keep_ids)
        if keep:
            q = q.where(TradeOpportunity.id.notin_(keep))
        await session.execute(q.values(isLatest=False))
        for r in rows:
            session.add(r)
        await session.flush()

    async def latest(self, session: AsyncSession, codes: Iterable[str] | None = None) -> list[TradeOpportunity]:
        q = (
            select(TradeOpportunity)
            .where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.isLatest.is_(True))
            .order_by(TradeOpportunity.underlyingCode, TradeOpportunity.rank.asc())
        )
        if codes is not None:
            q = q.where(TradeOpportunity.underlyingCode.in_([c.upper() for c in codes]))
        return list((await session.execute(q)).scalars().all())

    async def fresh(
        self, session: AsyncSession, codes: Iterable[str], created_since: datetime, now: datetime
    ) -> list[TradeOpportunity]:
        """Latest, still-PENDING, unexpired rows created at/after `created_since` -- the session loop's read.
        Served by the partial index ix_trade_opportunities_loop_fresh (created_at)."""
        q = (
            select(TradeOpportunity)
            .where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.isLatest.is_(True))
            .where(TradeOpportunity.outcome == "PENDING")
            .where(TradeOpportunity.createdAt >= created_since)
            .where(TradeOpportunity.validUntil > now)
            .where(TradeOpportunity.underlyingCode.in_([c.upper() for c in codes]))
            .order_by(TradeOpportunity.createdAt.desc(), TradeOpportunity.rank.asc())
        )
        return list((await session.execute(q)).scalars().all())

    async def pending(self, session: AsyncSession) -> list[TradeOpportunity]:
        res = await session.execute(
            select(TradeOpportunity).where(TradeOpportunity.status == 1).where(TradeOpportunity.outcome == "PENDING")
        )
        return list(res.scalars().all())

    async def get(self, session: AsyncSession, opp_id: int) -> TradeOpportunity | None:
        res = await session.execute(
            select(TradeOpportunity).where(TradeOpportunity.id == opp_id).where(TradeOpportunity.status == 1)
        )
        return res.scalar_one_or_none()

    async def for_master(
        self, session: AsyncSession, master_id: int, iteration_no: int | None = None
    ) -> list[TradeOpportunity]:
        q = (
            select(TradeOpportunity)
            .where(TradeOpportunity.status == 1)
            .where(TradeOpportunity.masterId == master_id)
        )
        if iteration_no is not None:
            q = q.where(TradeOpportunity.iterationNo == iteration_no)
        q = q.order_by(TradeOpportunity.iterationNo.desc(), TradeOpportunity.rank.asc())
        return list((await session.execute(q)).scalars().all())


class OpportunityIterationRepository:
    """Reads and writes opportunity_iterations (one diagnostics row per iteration)."""

    async def save(self, session: AsyncSession, row: OpportunityIteration) -> OpportunityIteration:
        session.add(row)
        await session.flush()
        return row


class OpportunityMasterRepository:
    """Reads and writes opportunity_masters (one row per card per Start)."""

    async def get(self, session: AsyncSession, master_id: int) -> OpportunityMaster | None:
        res = await session.execute(
            select(OpportunityMaster).where(OpportunityMaster.id == master_id).where(OpportunityMaster.status == 1)
        )
        return res.scalar_one_or_none()

    async def save(self, session: AsyncSession, m: OpportunityMaster) -> OpportunityMaster:
        session.add(m)
        await session.flush()
        return m

    async def next_session_no(self, session: AsyncSession, trade_date: str, code: str) -> int:
        res = await session.execute(
            select(func.coalesce(func.max(OpportunityMaster.sessionNo), 0))
            .where(OpportunityMaster.tradeDate == trade_date)
            .where(OpportunityMaster.underlyingCode == code)
            .where(OpportunityMaster.status == 1)
        )
        return int(res.scalar_one()) + 1

    async def running(
        self, session: AsyncSession, trade_date: str | None = None, codes: Iterable[str] | None = None
    ) -> list[OpportunityMaster]:
        q = select(OpportunityMaster).where(OpportunityMaster.status == 1).where(OpportunityMaster.state == "RUNNING")
        if trade_date:
            q = q.where(OpportunityMaster.tradeDate == trade_date)
        if codes is not None:
            q = q.where(OpportunityMaster.underlyingCode.in_([c.upper() for c in codes]))
        return list((await session.execute(q.order_by(OpportunityMaster.id))).scalars().all())

    async def latest_for_day(self, session: AsyncSession, trade_date: str) -> dict[str, OpportunityMaster]:
        """The newest master (highest sessionNo) of each underlying for that day."""
        res = await session.execute(
            select(OpportunityMaster)
            .where(OpportunityMaster.status == 1)
            .where(OpportunityMaster.tradeDate == trade_date)
            .order_by(OpportunityMaster.underlyingCode, OpportunityMaster.sessionNo.desc())
        )
        out: dict[str, OpportunityMaster] = {}
        for m in res.scalars().all():
            out.setdefault(m.underlyingCode, m)
        return out

    async def close_stale_days(self, session: AsyncSession, today: str, now: datetime) -> int:
        """Masters still RUNNING from an earlier day are stopped: a session never crosses midnight."""
        res = await session.execute(
            update(OpportunityMaster)
            .where(OpportunityMaster.state == "RUNNING")
            .where(OpportunityMaster.tradeDate < today)
            .values(state="STOPPED", stopReason="DAY_ENDED", stoppedAt=now)
        )
        return res.rowcount or 0


def make_ref(code: str, master: OpportunityMaster, iteration: int, rank: int) -> str:
    """Readable id such as OP-NIFTY-20261029-S01-I0005-01 (day, session, iteration, rank)."""
    return f"OP-{code}-{master.tradeDate.replace('-', '')}-S{master.sessionNo:02d}-I{iteration:04d}-{rank:02d}"


def risk_level(confidence: int, reward_risk: float, spread_pct: float) -> str:
    if confidence >= 80 and reward_risk >= 2 and spread_pct <= 2:
        return "LOW"
    if confidence >= 70 and reward_risk >= 1.5:
        return "MEDIUM"
    return "HIGH"


opportunity_repository = OpportunityRepository()
opportunity_master_repository = OpportunityMasterRepository()
opportunity_iteration_repository = OpportunityIterationRepository()

