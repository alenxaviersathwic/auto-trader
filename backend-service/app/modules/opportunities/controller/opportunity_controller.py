from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.filter.filter_builder import FilterBuilder
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.opportunities.entity.opportunity_entity import OpportunityMaster, TradeOpportunity
from app.modules.opportunities.schema.opportunity_schema import (
    OpportunityFilter,
    OpportunityMasterFilter,
    StartOpportunityRequest,
)
from app.modules.opportunities.service.run_service import opportunity_run_service as svc

opportunity_router = APIRouter(tags=["Opportunities"])
OK = status.HTTP_200_OK


# ───────────────────────── card sessions (opportunity_masters) ─────────────────────────
@opportunity_router.post("/opportunities/research-top", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def research_top(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    """Best underlyings from the Research Engine: top 5 INDEX + top 3 COMMODITY."""
    return success(data=await svc.research_top(session), message="Research top underlyings retrieved")


@opportunity_router.post("/opportunities/masters/today", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def todays_masters(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    """Today's newest session (master) per underlying, with live opportunity counts."""
    return success(data=await svc.today(session), message="Today's opportunity sessions retrieved")


@opportunity_router.post("/opportunities/masters/start", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def start_masters(
    body: StartOpportunityRequest | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    """Creates a NEW master row per card (all Research cards, or body.underlyings). The client then iterates them."""
    res = await svc.start(body or StartOpportunityRequest(), session)
    return success(data=res, message=f"{len(res['masters'])} card session(s) started" if res["started"]
                   else res.get("message", res["reason"]))


@opportunity_router.post("/opportunities/masters/{master_id}/iterate", response_model=ApiResponse[dict[str, Any]],
                         status_code=OK)
async def iterate_master(master_id: int) -> ApiResponse[dict[str, Any]]:
    """Runs ONE iteration for one card and returns the updated master. 409 if it is already iterating."""
    res = await svc.iterate(master_id)
    return success(data=res, message="Iteration completed" if res["ran"] else "Card is stopped; nothing ran")


@opportunity_router.post("/opportunities/masters/{master_id}/stop", response_model=ApiResponse[dict[str, Any]],
                         status_code=OK)
async def stop_master(master_id: int, session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.stop(session, master_id), message="Card session stopped")


@opportunity_router.post("/opportunities/masters/stop-all", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def stop_all_masters(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.stop_all(session), message="All running card sessions stopped")


@opportunity_router.post("/opportunities/masters/search", response_model=ApiResponse[PageResult[dict[str, Any]]],
                         status_code=OK)
async def search_masters(
    filter_body: OpportunityMasterFilter | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[PageResult[dict[str, Any]]]:
    """Card-session history, newest first."""
    f = filter_body or OpportunityMasterFilter()
    q = select(OpportunityMaster)
    if f.underlyingCode:
        q = q.where(OpportunityMaster.underlyingCode == f.underlyingCode.upper())
    if f.tradeDate:
        q = q.where(OpportunityMaster.tradeDate == f.tradeDate)
    if f.state:
        q = q.where(OpportunityMaster.state == f.state.upper())
    items, total = await FilterBuilder.execute_paged_query(
        session=session, entity_class=OpportunityMaster, filter_obj=f, search_fields=["underlyingCode"],
        allowed_sort_fields=["createdAt", "tradeDate", "iterationsCompleted", "opportunitiesTotal"], base_query=q,
    )
    page = PageResult(list=[svc.master_dict(i) for i in items], page=f.page, limit=f.limit,
                      totalPages=-(-total // f.limit), totalItems=total)
    return success(data=page, message="Card sessions retrieved")


# ───────────────────────── opportunities (trade_opportunities) ─────────────────────────
@opportunity_router.get("/opportunities/latest", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def latest_opportunities(
    underlying: str | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.latest(session, underlying.upper() if underlying else None),
                   message="Latest opportunities retrieved")


@opportunity_router.post("/opportunities/search", response_model=ApiResponse[PageResult[dict[str, Any]]],
                         status_code=OK)
async def search_opportunities(
    filter_body: OpportunityFilter | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[PageResult[dict[str, Any]]]:
    """trade_opportunities history, filterable by masterId / underlyingCode / outcome / latestOnly."""
    f = filter_body or OpportunityFilter()
    q = select(TradeOpportunity)
    if f.masterId:
        q = q.where(TradeOpportunity.masterId == f.masterId)
    if f.underlyingCode:
        q = q.where(TradeOpportunity.underlyingCode == f.underlyingCode.upper())
    if f.outcome:
        q = q.where(TradeOpportunity.outcome == f.outcome.upper())
    if f.latestOnly:
        q = q.where(TradeOpportunity.isLatest.is_(True))
    items, total = await FilterBuilder.execute_paged_query(
        session=session, entity_class=TradeOpportunity, filter_obj=f, search_fields=["ref", "strategy"],
        allowed_sort_fields=["rank", "confidence", "createdAt", "iterationNo"], base_query=q,
    )
    now = datetime.now(UTC)
    page = PageResult(list=[svc.to_dict(i, now) for i in items], page=f.page, limit=f.limit,
                      totalPages=-(-total // f.limit), totalItems=total)
    return success(data=page, message="Opportunities retrieved")

