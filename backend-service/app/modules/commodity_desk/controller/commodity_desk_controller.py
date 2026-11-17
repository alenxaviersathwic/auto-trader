from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.commodity_desk.schema.commodity_desk_schema import (
    DeskDecisionResponse,
    DeskDecisionSearchFilter,
    DeskLatestResponse,
    DeskLiveResponse,
    MarketMoveResponse,
    MarketMoveSearchFilter,
)
from app.modules.commodity_desk.service.commodity_desk_service import commodity_desk_service

commodity_desk_router = APIRouter(prefix="/commodity-desk", tags=["Commodity Desk (sub-agents + head trader)"])


@commodity_desk_router.get("/latest", response_model=ApiResponse[DeskLatestResponse], status_code=status.HTTP_200_OK,
                           summary="Newest desk decision per commodity and recent sudden moves")
async def latest(hours: float = Query(default=6, gt=0, le=48), db: AsyncSession = Depends(get_db)):
    return success(data=await commodity_desk_service.latest(db, hours), message="Commodity Desk latest")


@commodity_desk_router.get("/live", response_model=ApiResponse[DeskLiveResponse], status_code=status.HTTP_200_OK,
                           summary="What every desk and news check is doing right now")
async def live():
    return success(data=commodity_desk_service.live(), message="Commodity Desk live")


@commodity_desk_router.post("/decisions/search", response_model=ApiResponse[PageResult[DeskDecisionResponse]],
                            status_code=status.HTTP_200_OK, summary="Search desk decisions")
async def search_decisions(filter_obj: DeskDecisionSearchFilter, db: AsyncSession = Depends(get_db)):
    return success(data=await commodity_desk_service.search_decisions(db, filter_obj), message="Desk decisions fetched")


@commodity_desk_router.post("/moves/search", response_model=ApiResponse[PageResult[MarketMoveResponse]],
                            status_code=status.HTTP_200_OK, summary="Search sudden market moves")
async def search_moves(filter_obj: MarketMoveSearchFilter, db: AsyncSession = Depends(get_db)):
    return success(data=await commodity_desk_service.search_moves(db, filter_obj), message="Market moves fetched")
