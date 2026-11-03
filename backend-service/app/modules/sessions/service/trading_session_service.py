from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception.app_exceptions import NotFoundException
from app.core.pagination.page_result import PageResult
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.repository.trading_session_repository import TradingSessionRepository
from app.modules.sessions.schema.trading_session_schema import (
    TradingSessionCreateRequest,
    TradingSessionResponse,
    TradingSessionSearchFilter,
    TradingSessionUpdateRequest,
)

_UPDATABLE_FIELDS = (
    "name",
    "capital",
    "maxLossPercentage",
    "underlyings",
    "commodityItems",
    "sessionType",
    "routeThroughUpstox",
)


class TradingSessionService:
    """Business service for creating and managing TradingSession records."""

    def __init__(self, repository: TradingSessionRepository | None = None):
        self.repo = repository or TradingSessionRepository()

    @staticmethod
    def to_response(entity: TradingSession) -> TradingSessionResponse:
        """Transforms TradingSession entity into the response envelope."""
        return TradingSessionResponse(
            id=entity.id,
            name=entity.name,
            tradeDate=entity.tradeDate,
            userId=entity.userId,
            capital=entity.capital,
            maxLossPercentage=entity.maxLossPercentage,
            scope=entity.scope,
            underlyings=entity.underlyings or [],
            commodityItems=entity.commodityItems or [],
            sessionType=entity.sessionType,
            routeThroughUpstox=entity.routeThroughUpstox,
            sessionStatus=entity.sessionStatus,
            haltReason=entity.haltReason,
            haltedAt=entity.haltedAt,
            closedAt=entity.closedAt,
            status=entity.status.name,
            createdAt=entity.createdAt,
        )

    async def create(
        self, session: AsyncSession, request: TradingSessionCreateRequest
    ) -> TradingSessionResponse:
        """Creates a trading session. A blank name is auto-generated from date + scope selection."""
        name = (request.name or "").strip()
        if not name:
            picked = request.underlyings or request.commodityItems or [request.scope.upper()]
            name = f"{request.tradeDate} — {'/'.join(picked)}"

        entity = TradingSession(
            name=name,
            tradeDate=request.tradeDate,
            userId=request.userId,
            capital=request.capital,
            maxLossPercentage=request.maxLossPercentage,
            scope=request.scope.upper(),
            underlyings=request.underlyings,
            commodityItems=request.commodityItems,
            sessionType=request.sessionType.upper(),
            routeThroughUpstox=request.routeThroughUpstox,
            sessionStatus="ACTIVE",
        )
        saved = await self.repo.save(session, entity)
        return self.to_response(saved)

    async def get_by_id(self, session: AsyncSession, session_id: int) -> TradingSessionResponse:
        """Fetch a single trading session, raising NotFoundException if missing."""
        entity = await self.repo.get_by_id(session, session_id)
        if not entity:
            raise NotFoundException(message=f"Trading session {session_id} not found")
        return self.to_response(entity)

    async def search(
        self, session: AsyncSession, filter_obj: TradingSessionSearchFilter
    ) -> PageResult[TradingSessionResponse]:
        """Paged search over trading sessions."""
        page_result = await self.repo.search(session, filter_obj)
        return PageResult(
            list=[self.to_response(e) for e in page_result.list],
            page=page_result.page,
            limit=page_result.limit,
            totalPages=page_result.totalPages,
            totalItems=page_result.totalItems,
        )

    async def update(
        self, session: AsyncSession, session_id: int, request: TradingSessionUpdateRequest
    ) -> TradingSessionResponse:
        """Updates only the fields provided on the request."""
        entity = await self.repo.get_by_id(session, session_id)
        if not entity:
            raise NotFoundException(message=f"Trading session {session_id} not found")

        data = request.model_dump(exclude_unset=True)
        for field in _UPDATABLE_FIELDS:
            if field in data and data[field] is not None:
                value = data[field]
                if field == "sessionType":
                    value = value.upper()
                setattr(entity, field, value)

        if data.get("sessionStatus"):
            entity.sessionStatus = data["sessionStatus"].upper()
            if entity.sessionStatus == "CLOSED" and entity.closedAt is None:
                entity.closedAt = datetime.now(UTC)

        saved = await self.repo.save(session, entity)
        return self.to_response(saved)

    async def delete(self, session: AsyncSession, session_id: int) -> None:
        """Soft deletes a trading session."""
        entity = await self.repo.get_by_id(session, session_id)
        if not entity:
            raise NotFoundException(message=f"Trading session {session_id} not found")
        await self.repo.soft_delete(session, entity)
