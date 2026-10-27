from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.exception.app_exceptions import AppException
from app.core.filter.filter_builder import FilterBuilder
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.suggestion.entity.suggestion_entity import SUGGESTION_ENTITIES
from app.modules.suggestion.repository.suggestion_repository import entity_for
from app.modules.suggestion.schema.suggestion_schema import (
    StartSuggestionRequest,
    StopSuggestionRequest,
    SuggestionFilter,
)
from app.modules.suggestion.service.run_service import suggestion_run_service as svc

suggestion_router = APIRouter(tags=["Suggestion"])


@suggestion_router.post("/suggestion/run", response_model=ApiResponse[dict[str, Any]], status_code=status.HTTP_200_OK)
async def run_suggestion_engine(
    body: StartSuggestionRequest | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    """Checks Research has data, then starts the suggestion loop (runs until /suggestion/stop)."""
    res = await svc.start(body or StartSuggestionRequest(), session)
    return success(data=res, message="Suggestion loop started" if res["started"] else res.get("message", res["reason"]))


@suggestion_router.post("/suggestion/stop", response_model=ApiResponse[dict[str, Any]], status_code=status.HTTP_200_OK)
async def stop_suggestion_engine(
    body: StopSuggestionRequest | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.stop(session, body.underlyings if body else None),
                   message="Suggestion loop stop handled")


@suggestion_router.get("/suggestion/run-status", response_model=ApiResponse[dict[str, Any]], status_code=status.HTTP_200_OK)
async def suggestion_run_status(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.status(session), message="Suggestion engine status retrieved")


@suggestion_router.get("/suggestion/latest", response_model=ApiResponse[dict[str, Any]], status_code=status.HTTP_200_OK)
async def latest_suggestions(
    underlying: str | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[dict[str, Any]]:
    return success(data=await svc.latest(session, underlying.upper() if underlying else None), message="Latest suggestions retrieved")


@suggestion_router.post("/suggestion/search", response_model=ApiResponse[PageResult[dict[str, Any]]],
                        status_code=status.HTTP_200_OK)
async def search_suggestions(
    filter_body: SuggestionFilter | None = None, session: AsyncSession = Depends(get_db)
) -> ApiResponse[PageResult[dict[str, Any]]]:
    """History of one underlying's suggestion table (underlyingCode required), newest first."""
    f = filter_body or SuggestionFilter()
    if not f.underlyingCode or f.underlyingCode.upper() not in SUGGESTION_ENTITIES:
        raise AppException("underlyingCode is required and must be a known underlying", status_code=400)
    ent = entity_for(f.underlyingCode)
    q = select(ent)
    if f.runId:
        q = q.where(ent.runId == f.runId)
    if f.outcome:
        q = q.where(ent.outcome == f.outcome.upper())
    if f.latestOnly:
        q = q.where(ent.isLatest.is_(True))
    items, total = await FilterBuilder.execute_paged_query(
        session=session, entity_class=ent, filter_obj=f, search_fields=["ref", "strategy"],
        allowed_sort_fields=["rank", "confidence", "createdAt"], base_query=q,
    )
    now = datetime.now(UTC)
    page = PageResult(
        list=[svc.to_dict(i, now) for i in items], page=f.page, limit=f.limit,
        totalPages=-(-total // f.limit), totalItems=total,
    )
    return success(data=page, message="Suggestions retrieved")


@suggestion_router.get("/suggestion/underlyings", response_model=ApiResponse[dict[str, Any]],
                       status_code=status.HTTP_200_OK)
async def suggestion_underlyings(session: AsyncSession = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    """Top 5 INDEX + top 3 COMMODITY from Research with suggestion counts (default screen)."""
    return success(data=await svc.underlyings(session), message="Underlyings retrieved")
