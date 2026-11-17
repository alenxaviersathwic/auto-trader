from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination.page_result import PageResult
from app.modules.commodity_desk.repository.commodity_desk_repository import commodity_desk_repository as repo
from app.modules.commodity_desk.schema.commodity_desk_schema import (
    DeskDecisionResponse,
    DeskDecisionSearchFilter,
    DeskLatestResponse,
    DeskLiveResponse,
    MarketMoveResponse,
    MarketMoveSearchFilter,
)

LATEST_HOURS = 6


class CommodityDeskService:
    """Read side of the Commodity Desk for the API (the desk itself runs inside the scans: desk_service.run)."""

    def live(self) -> DeskLiveResponse:
        from app.modules.commodity_desk.service import desk_service, move_watch

        return DeskLiveResponse(serverTime=datetime.now(UTC), desks=desk_service.live(), newsChecks=move_watch.active())

    async def latest(self, session: AsyncSession, hours: float = LATEST_HOURS) -> DeskLatestResponse:
        since = datetime.now(UTC) - timedelta(hours=hours)
        decisions = await repo.latest_decisions(session, since)
        moves = await repo.moves_since(session, since)
        return DeskLatestResponse(decisions=[DeskDecisionResponse.model_validate(d) for d in decisions],
                                  moves=[MarketMoveResponse.model_validate(m) for m in moves[:30]])

    async def search_decisions(self, session: AsyncSession, f: DeskDecisionSearchFilter) -> PageResult[DeskDecisionResponse]:
        page = await repo.search_decisions(session, f)
        return PageResult(list=[DeskDecisionResponse.model_validate(d) for d in page.list], page=page.page,
                          limit=page.limit, totalPages=page.totalPages, totalItems=page.totalItems)

    async def search_moves(self, session: AsyncSession, f: MarketMoveSearchFilter) -> PageResult[MarketMoveResponse]:
        page = await repo.search_moves(session, f)
        return PageResult(list=[MarketMoveResponse.model_validate(m) for m in page.list], page=page.page,
                          limit=page.limit, totalPages=page.totalPages, totalItems=page.totalItems)


commodity_desk_service = CommodityDeskService()
