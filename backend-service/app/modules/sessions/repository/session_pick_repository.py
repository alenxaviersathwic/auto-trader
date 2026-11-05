import math
from datetime import datetime

from sqlalchemy import asc, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.sessions.entity.session_pick_entity import SessionPick, SessionPickArchive
from app.modules.sessions.schema.session_pick_schema import SessionPickSearchFilter


class SessionPickRepository:
    """Repository handling database operations for SessionPick."""

    async def get_by_id(self, session: AsyncSession, pick_id: int) -> SessionPick | None:
        res = await session.execute(
            select(SessionPick).where(SessionPick.id == pick_id).where(SessionPick.status == EntityStatus.ACTIVE)
        )
        return res.scalar_one_or_none()

    async def open_picks(self, session: AsyncSession, session_id: int) -> list[SessionPick]:
        """OFFERED and LOCKED picks of a session (the only states the loop has to reason about)."""
        res = await session.execute(
            select(SessionPick)
            .where(SessionPick.sessionId == session_id)
            .where(SessionPick.status == EntityStatus.ACTIVE)
            .where(SessionPick.pickState.in_(("OFFERED", "LOCKED")))
            .order_by(SessionPick.id)
        )
        return list(res.scalars().all())

    async def offered_opportunity_ids(self, session: AsyncSession, session_id: int) -> set[int]:
        """Every opportunity ever offered to this session, in any state: it is never offered twice."""
        res = await session.execute(
            select(SessionPick.opportunityId)
            .where(SessionPick.sessionId == session_id)
            .where(SessionPick.status == EntityStatus.ACTIVE)
        )
        return {int(x) for x in res.scalars().all()}

    async def save(self, session: AsyncSession, entity: SessionPick) -> SessionPick:
        session.add(entity)
        await session.flush()
        return entity

    async def search(
        self, session: AsyncSession, session_id: int, filter_obj: SessionPickSearchFilter
    ) -> PageResult[SessionPick]:
        """A running session's picks live in session_picks; once it is finished they are in the archive table."""
        live = await self._search(session, SessionPick, session_id, filter_obj)
        if live.totalItems > 0:
            return live
        archived = await self._search(session, SessionPickArchive, session_id, filter_obj)
        return archived if archived.totalItems > 0 else live

    async def archive_finished(self, session: AsyncSession, today: str, now: datetime) -> dict[str, int]:
        """
        Move the picks of every FINISHED session from session_picks to session_picks_archive, in one statement
        (delete + insert, so nothing is lost or duplicated). Sessions still inside their trading hours keep their
        rows. A session is finished when it is closed / deleted, dated before `today`, or past its close time; a
        still-ACTIVE one past its close time is closed first. Picks still OFFERED are stored as EXPIRED.
        """
        closed = await session.execute(
            text("UPDATE trading_sessions SET session_status = 'CLOSED', closed_at = :now "
                 "WHERE session_status = 'ACTIVE' AND (close_at <= :now OR trade_date < :today)"),
            {"now": now, "today": today},
        )
        cols = [c.name for c in SessionPick.__table__.columns]
        select_list = ", ".join(
            "CASE WHEN m.pick_state = 'OFFERED' THEN 'EXPIRED' ELSE m.pick_state END" if c == "pick_state" else f"m.{c}"
            for c in cols
        )
        moved = await session.execute(
            text(
                "WITH moved AS ("
                " DELETE FROM session_picks p USING trading_sessions s"
                " WHERE p.session_id = s.id"
                "   AND (s.session_status <> 'ACTIVE' OR s.status <> 1 OR s.trade_date < :today OR s.close_at <= :now)"
                " RETURNING p.*)"
                f" INSERT INTO session_picks_archive ({', '.join(cols)}) SELECT {select_list} FROM moved m"
            ),
            {"now": now, "today": today},
        )
        return {"sessionsClosed": closed.rowcount or 0, "picksArchived": moved.rowcount or 0}

    async def _search(
        self, session: AsyncSession, model, session_id: int, filter_obj: SessionPickSearchFilter
    ) -> PageResult:
        target_status = filter_obj.status or EntityStatus.ACTIVE
        base = (
            select(model)
            .where(model.sessionId == session_id)
            .where(model.status == target_status)
        )
        if filter_obj.pickState:
            base = base.where(model.pickState == filter_obj.pickState.upper())
        if filter_obj.dateFilter:
            if filter_obj.dateFilter.from_ is not None:
                base = base.where(model.createdAt >= filter_obj.dateFilter.from_)
            if filter_obj.dateFilter.to is not None:
                base = base.where(model.createdAt <= filter_obj.dateFilter.to)
        if filter_obj.query and filter_obj.query.strip():
            term = f"%{filter_obj.query.strip()}%"
            base = base.where(model.underlyingCode.ilike(term) | model.strategy.ilike(term))

        total_items = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one_or_none() or 0

        sort_by = filter_obj.sortBy or "createdAt"
        allowed = {"createdAt", "offeredAt", "lockedAt", "confidence", "expectedNet"}
        if sort_by not in allowed:
            raise ValidationException(message=f"Invalid sortBy field '{sort_by}'. Allowed fields: {sorted(allowed)}")
        col = getattr(model, sort_by)
        order = desc(col) if (filter_obj.sortDir or "desc").lower() == "desc" else asc(col)

        rows = list((await session.execute(
            base.order_by(order).offset(filter_obj.page * filter_obj.limit).limit(filter_obj.limit)
        )).scalars().all())
        limit = filter_obj.limit if filter_obj.limit > 0 else 10
        return PageResult(
            list=rows, page=filter_obj.page, limit=limit,
            totalPages=math.ceil(total_items / limit) if total_items > 0 else 0, totalItems=total_items,
        )
