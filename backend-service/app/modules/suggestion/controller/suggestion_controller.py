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
from app.modules.suggestion.entity.suggestion_entity import SuggestionMaster, TradeSuggestion
from app.modules.suggestion.schema.suggestion_schema import (
    StartSuggestionRequest,
    SuggestionFilter,
    SuggestionMasterFilter,
)
from app.modules.suggestion.service.run_service import suggestion_run_service as svc

suggestion_router = APIRouter(tags=["Suggestion"])
OK = status.HTTP_200_OK


# ───────────────────────── card sessions (suggestion_masters) ─────────────────────────
@suggestion_router.get("/suggestion/research-top", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def research_top(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    """Best underlyings from the Research Engine: top 5 INDEX + top 3 COMMODITY."""
    return success(data=await svc.research_top(session), message="Research top underlyings retrieved")


@suggestion_router.get("/suggestion/masters/today", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def todays_masters(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    """Today's newest session (master) per underlying, with live suggestion counts."""
    return success(data=await svc.today(session), message="Today's suggestion sessions retrieved")


@suggestion_router.post("/suggestion/masters/start", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def start_masters(
    body: StartSuggestionRequest | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    """Creates a NEW master row per card (all Research cards, or body.underlyings). The client then iterates them."""
    res = await svc.start(body or StartSuggestionRequest(), session)
    return success(data=res, message=f"{len(res['masters'])} card session(s) started" if res["started"]
                   else res.get("message", res["reason"]))


@suggestion_router.post("/suggestion/masters/{master_id}/iterate", response_model=ApiResponse[dict[str, Any]],
                        status_code=OK)
async def iterate_master(master_id: int) -> ApiResponse[dict[str, Any]]:
    """Runs ONE iteration for one card and returns the updated master. 409 if it is already iterating."""
    res = await svc.iterate(master_id)
    return success(data=res, message="Iteration completed" if res["ran"] else "Card is stopped; nothing ran")


@suggestion_router.post("/suggestion/masters/{master_id}/stop", response_model=ApiResponse[dict[str, Any]],
                        status_code=OK)
async def stop_master(master_id: int, session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.stop(session, master_id), message="Card session stopped")


@suggestion_router.post("/suggestion/masters/stop-all", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def stop_all_masters(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.stop_all(session), message="All running card sessions stopped")


@suggestion_router.post("/suggestion/masters/search", response_model=ApiResponse[PageResult[dict[str, Any]]],
                        status_code=OK)
async def search_masters(
    filter_body: SuggestionMasterFilter | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[PageResult[dict[str, Any]]]:
    """Card-session history, newest first."""
    f = filter_body or SuggestionMasterFilter()
    q = select(SuggestionMaster)
    if f.underlyingCode:
        q = q.where(SuggestionMaster.underlyingCode == f.underlyingCode.upper())
    if f.tradeDate:
        q = q.where(SuggestionMaster.tradeDate == f.tradeDate)
    if f.state:
        q = q.where(SuggestionMaster.state == f.state.upper())
    items, total = await FilterBuilder.execute_paged_query(
        session=session, entity_class=SuggestionMaster, filter_obj=f, search_fields=["underlyingCode"],
        allowed_sort_fields=["createdAt", "tradeDate", "iterationsCompleted", "suggestionsTotal"], base_query=q,
    )
    page = PageResult(list=[svc.master_dict(i) for i in items], page=f.page, limit=f.limit,
                      totalPages=-(-total // f.limit), totalItems=total)
    return success(data=page, message="Card sessions retrieved")


# ───────────────────────── suggestions (trade_suggestions) ─────────────────────────
@suggestion_router.get("/suggestion/latest", response_model=ApiResponse[dict[str, Any]], status_code=OK)
async def latest_suggestions(
    underlying: str | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.latest(session, underlying.upper() if underlying else None),
                   message="Latest suggestions retrieved")


@suggestion_router.post("/suggestion/search", response_model=ApiResponse[PageResult[dict[str, Any]]],
                        status_code=OK)
async def search_suggestions(
    filter_body: SuggestionFilter | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[PageResult[dict[str, Any]]]:
    """trade_suggestions history, filterable by masterId / underlyingCode / outcome / latestOnly."""
    f = filter_body or SuggestionFilter()
    q = select(TradeSuggestion)
    if f.masterId:
        q = q.where(TradeSuggestion.masterId == f.masterId)
    if f.underlyingCode:
        q = q.where(TradeSuggestion.underlyingCode == f.underlyingCode.upper())
    if f.outcome:
        q = q.where(TradeSuggestion.outcome == f.outcome.upper())
    if f.latestOnly:
        q = q.where(TradeSuggestion.isLatest.is_(True))
    items, total = await FilterBuilder.execute_paged_query(
        session=session, entity_class=TradeSuggestion, filter_obj=f, search_fields=["ref", "strategy"],
        allowed_sort_fields=["rank", "confidence", "createdAt", "iterationNo"], base_query=q,
    )
    now = datetime.now(UTC)
    page = PageResult(list=[svc.to_dict(i, now) for i in items], page=f.page, limit=f.limit,
                      totalPages=-(-total // f.limit), totalItems=total)
    return success(data=page, message="Suggestions retrieved")
