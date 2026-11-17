from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.autopsy.schema.learning_schema import (
    AutopsySearchFilter,
    GuardSearchFilter,
    ScorecardSearchFilter,
    SetupGuardResponse,
    SetupScorecardResponse,
    TradeAutopsyResponse,
)
from app.modules.autopsy.service.learning_service import learning_service

learning_router = APIRouter(prefix="/learning", tags=["Learning (each session manager's autopsy sub-agent)"])


@learning_router.post("/autopsies/search", response_model=ApiResponse[PageResult[TradeAutopsyResponse]],
                      status_code=status.HTTP_200_OK, summary="Search trade autopsies")
async def search_autopsies(filter_obj: AutopsySearchFilter, db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.search_autopsies(db, filter_obj), message="Autopsies fetched")


@learning_router.get("/autopsies/trade/{trade_id}", response_model=ApiResponse[TradeAutopsyResponse],
                     status_code=status.HTTP_200_OK, summary="Autopsy of one trade")
async def autopsy_for_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.autopsy_for_trade(db, trade_id), message="Autopsy fetched")


@learning_router.post("/scorecards/search", response_model=ApiResponse[PageResult[SetupScorecardResponse]],
                      status_code=status.HTTP_200_OK, summary="Search setup scorecards")
async def search_scorecards(filter_obj: ScorecardSearchFilter, db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.search_scorecards(db, filter_obj), message="Scorecards fetched")


@learning_router.post("/scorecards/{setup}/resume", response_model=ApiResponse[SetupScorecardResponse],
                      status_code=status.HTTP_200_OK, summary="Resume a paused setup")
async def resume_setup(setup: str, managerCode: str | None = Query(default=None, description="Session manager; "
                                                                 "default: the trader that owns the setup"),
                       db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.resume_setup(db, setup, managerCode), message=f"{setup} resumed")


@learning_router.post("/guards/search", response_model=ApiResponse[PageResult[SetupGuardResponse]],
                      status_code=status.HTTP_200_OK, summary="Search learned guards")
async def search_guards(filter_obj: GuardSearchFilter, db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.search_guards(db, filter_obj), message="Guards fetched")


@learning_router.post("/guards/{guard_id}/apply", response_model=ApiResponse[SetupGuardResponse],
                      status_code=status.HTTP_200_OK, summary="Apply a learned guard")
async def apply_guard(guard_id: int, db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.apply_guard(db, guard_id), message="Guard applied")


@learning_router.post("/guards/{guard_id}/reject", response_model=ApiResponse[SetupGuardResponse],
                      status_code=status.HTTP_200_OK, summary="Reject a learned guard")
async def reject_guard(guard_id: int, db: AsyncSession = Depends(get_db)):
    return success(data=await learning_service.reject_guard(db, guard_id), message="Guard rejected")
