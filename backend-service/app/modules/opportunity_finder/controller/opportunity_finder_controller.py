from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.opportunity_finder.schema.opportunity_finder_schema import (
    OpportunityFinderResponse,
    OpportunityFinderSearchFilter,
    OpportunityFinderUpdateRequest,
)
from app.modules.opportunity_finder.service.opportunity_finder_service import opportunity_finder_service as svc

opportunity_finder_router = APIRouter(prefix="/opportunity-finders", tags=["Opportunity finders"])
OK = status.HTTP_200_OK


@opportunity_finder_router.get("", response_model=ApiResponse[list[OpportunityFinderResponse]], status_code=OK,
                               summary="All finders, or only those working on one market (optionType)")
async def list_finders(optionType: Optional[str] = Query(default=None, description="INDEX or COMMODITY"),
                       db: AsyncSession = Depends(get_db)):
    return success(data=await svc.list_for(db, optionType), message="Opportunity finders fetched")


@opportunity_finder_router.post("/search", response_model=ApiResponse[PageResult[OpportunityFinderResponse]],
                                status_code=OK, summary="Search finders")
async def search_finders(filter_obj: OpportunityFinderSearchFilter, db: AsyncSession = Depends(get_db)):
    return success(data=await svc.search(db, filter_obj), message="Opportunity finders fetched")


@opportunity_finder_router.get("/{code}", response_model=ApiResponse[OpportunityFinderResponse], status_code=OK,
                               summary="One finder")
async def get_finder(code: str, db: AsyncSession = Depends(get_db)):
    return success(data=await svc.get(db, code), message="Opportunity finder fetched")


@opportunity_finder_router.put("/{code}", response_model=ApiResponse[OpportunityFinderResponse], status_code=OK,
                               summary="Update a finder (optionTypes, enabled, name)")
async def update_finder(code: str, body: OpportunityFinderUpdateRequest, db: AsyncSession = Depends(get_db)):
    return success(data=await svc.update(db, code, body), message="Opportunity finder updated")
