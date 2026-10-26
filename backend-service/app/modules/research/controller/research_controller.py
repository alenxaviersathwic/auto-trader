from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.core.exception.app_exceptions import AppException
from app.core.filter.filter_builder import FilterBuilder
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.research.entity.research_entity import ResearchCandidate
from app.modules.research.schema.research_schema import (
    ResearchCandidateFilter,
    StartRunRequest,
)
from app.modules.research.service.run_service import run_service

research_router = APIRouter(tags=["Research"])


# 1. RUN ENGINE (POST)
@research_router.post(
    "/research/run",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def trigger_research_engine(
    body: Optional[StartRunRequest] = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Triggers the research pipeline for specified or default scopes (INDEX, COMMODITY)."""
    scope = body.scope if body else ["INDEX", "COMMODITY"]
    params = body.model_dump(exclude_unset=True) if body else {"windowHours": 24, "topN": 5}
    res = await run_service.trigger_or_get_active_run(scope=scope, params=params, session=session)
    return success(data=res, message="Research engine pipeline running")


# 2. RUN STATUS (GET)
@research_router.get(
    "/research/run-status",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def get_engine_status(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Returns live status of current or most recent research run."""
    status_data = await run_service.get_current_status(session)
    return success(data=status_data, message="Research engine status retrieved")


# 3. CANCEL RUN (POST)
@research_router.post(
    "/research/cancel",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def cancel_engine_run(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Cancels any active research pipeline run."""
    res = await run_service.cancel_active_run(session)
    return success(data=res, message="Research cancellation handled")


# 4. SEARCH EVALUATED CANDIDATES (POST)
@research_router.post(
    "/research/search",
    response_model=ApiResponse[PageResult[Dict[str, Any]]],
    status_code=status.HTTP_200_OK,
)
async def search_candidates(
    filter_body: Optional[ResearchCandidateFilter] = None,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[PageResult[Dict[str, Any]]]:
    """Search evaluated research candidate entities sorted by latest score with filtering in UI."""
    f = filter_body or ResearchCandidateFilter()
    if not f.sortBy or f.sortBy == "createdAt":
        f.sortBy = "score"
        f.sortDir = "desc"

    scope_val = f.scope or f.underlyingType
    item_val = f.item or f.underlyingCode

    query = select(ResearchCandidate)

    if f.runId:
        query = query.where(ResearchCandidate.runId == f.runId)
    if scope_val:
        query = query.where(ResearchCandidate.underlyingType == scope_val.upper())
    if item_val:
        query = query.where(ResearchCandidate.underlyingCode == item_val.upper())
    if f.newsStatus:
        query = query.where(ResearchCandidate.newsStatus == f.newsStatus.upper())
    if f.suggested is not None:
        query = query.where(ResearchCandidate.suggested == f.suggested)
    if f.bearishWatch is not None:
        query = query.where(ResearchCandidate.bearishWatch == f.bearishWatch)
    if f.minScore is not None:
        query = query.where(ResearchCandidate.score >= f.minScore)

    items, total_items = await FilterBuilder.execute_paged_query(
        session=session,
        entity_class=ResearchCandidate,
        filter_obj=f,
        search_fields=["underlyingCode", "newsStatus", "direction", "scoreLabel", "thesis"],
        allowed_sort_fields=["score", "rank", "createdAt", "updatedAt", "positiveWeight", "negativeWeight"],
        base_query=query,
    )

    page_result = FilterBuilder.build_page_result(items, total_items, f)
    dict_items = [run_service._candidate_to_dict(c) for c in page_result.list]
    return success(
        data=PageResult(
            list=dict_items,
            page=page_result.page,
            limit=page_result.limit,
            totalPages=page_result.totalPages,
            totalItems=page_result.totalItems,
        ),
        message="Research candidates retrieved",
    )


# 5. GET CANDIDATE DETAIL (GET)
@research_router.get(
    "/research/candidates/{candidate_id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def get_candidate_detail(
    candidate_id: int,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Fetch complete candidate clearance details, supporting points, watch items, and verified claims."""
    res = await session.execute(
        select(ResearchCandidate).where(ResearchCandidate.id == candidate_id)
    )
    c = res.scalar_one_or_none()
    if not c:
        raise AppException(status_code=404, message="Candidate not found")

    data = run_service._candidate_to_dict(c)

    verified_claims = []
    for sp in c.supportingPoints or []:
        verified_claims.append({
            "id": sp.get("claimIds", [1])[0] if sp.get("claimIds") else 1,
            "statement": sp.get("text", ""),
            "stance": "BULLISH",
            "polarity": 1,
            "confidence": 1.0,
            "domain": "Market Intelligence",
            "quote": sp.get("text", ""),
        })
    for wi in c.watchItems or []:
        verified_claims.append({
            "id": wi.get("claimIds", [2])[0] if wi.get("claimIds") else 2,
            "statement": wi.get("text", ""),
            "stance": "BEARISH",
            "polarity": -1,
            "confidence": 1.0,
            "domain": "Risk Monitoring",
            "quote": wi.get("text", ""),
        })

    data["verifiedClaims"] = verified_claims
    return success(data=data, message="Candidate details retrieved")


# 6. GET LATEST RESULTS BY TYPE (GET)
@research_router.get(
    "/research/results/latest",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def get_latest_results(
    underlyingType: str = Query(default="INDEX", description="INDEX or COMMODITY"),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Fetch latest run results grouped by clearance status."""
    res = await run_service.get_latest_results(underlyingType, session)
    return success(data=res, message=f"Latest {underlyingType} research results retrieved")
