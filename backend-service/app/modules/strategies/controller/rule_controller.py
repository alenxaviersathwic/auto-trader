from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import created, success
from app.modules.strategies.schema.rule_schema import (
    CheckRulesRequest,
    CheckRulesResponse,
    RuleCreate,
    RuleDetailResponse,
    RuleFilter,
    RuleResponse,
    RuleUpdate,
    RuleVersionFilter,
    RuleVersionResponse,
)
from app.modules.strategies.schema.strategy_schema import AnalyzeConflictsRequest, SimilarSearchRequest
from app.modules.strategies.service.conflict_analyzer import ConflictAnalyzer
from app.modules.strategies.service.rule_service import RuleService
from app.modules.strategies.service.similarity_service import SimilarityService

rule_router = APIRouter(prefix="/rules", tags=["Rules"])

_rule_service = RuleService()
_similarity_service = SimilarityService()
_conflict_analyzer = ConflictAnalyzer()


@rule_router.post(
    "/search",
    response_model=ApiResponse[PageResult[RuleResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search rules with filters and pagination",
)
async def search_rules(
    filter_obj: RuleFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _rule_service.search(session, filter_obj)
    return success(data=page_res, message="Rules retrieved successfully")


@rule_router.post(
    "",
    response_model=ApiResponse[RuleDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new guardrail or condition block rule",
)
async def create_rule(
    payload: RuleCreate,
    session: AsyncSession = Depends(get_db),
):
    saved_rule = await _rule_service.create(session, payload)
    return created(data=saved_rule, message="Rule created successfully")


@rule_router.post(
    "/check",
    response_model=ApiResponse[CheckRulesResponse],
    status_code=status.HTTP_200_OK,
    summary="Check active guardrails against current context",
)
async def check_rules(
    payload: CheckRulesRequest,
    session: AsyncSession = Depends(get_db),
):
    check_res = await _rule_service.check_guardrails(session, payload)
    return success(data=check_res, message="Guardrails checked successfully")


@rule_router.get(
    "/{id}",
    response_model=ApiResponse[RuleDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get rule by ID with version and strategy usages",
)
async def get_rule_by_id(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    rule = await _rule_service.get_by_id(session, id)
    return success(data=rule, message="Rule retrieved successfully")


@rule_router.put(
    "/{id}",
    response_model=ApiResponse[RuleDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Update rule details or content (creates new version if changed)",
)
async def update_rule(
    id: int,
    payload: RuleUpdate,
    session: AsyncSession = Depends(get_db),
):
    updated = await _rule_service.update(session, id, payload)
    return success(data=updated, message="Rule updated successfully")


@rule_router.delete(
    "/{id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Soft delete rule (blocked if in use by active strategy)",
)
async def delete_rule(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    await _rule_service.delete(session, id)
    return success(data={"id": id, "deleted": True}, message="Rule deleted successfully")


@rule_router.post(
    "/{id}/versions/search",
    response_model=ApiResponse[PageResult[RuleVersionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search rule version history",
)
async def list_rule_versions(
    id: int,
    payload: RuleVersionFilter,
    session: AsyncSession = Depends(get_db),
):
    versions_page = await _rule_service.list_versions(session, id, payload)
    return success(data=versions_page, message="Rule versions retrieved")


@rule_router.post(
    "/similar",
    response_model=ApiResponse[list],
    status_code=status.HTTP_200_OK,
    summary="Find similar rules by conditions and triggers",
)
async def find_similar_rules(
    payload: SimilarSearchRequest,
    session: AsyncSession = Depends(get_db),
):
    similars = await _similarity_service.find_similar_rules(
        session=session,
        definition=payload.definition or {},
        meta=payload.meta,
        top_k=payload.topK,
    )
    return success(data=similars, message="Similar rules found")


@rule_router.post(
    "/analyze-conflicts",
    response_model=ApiResponse[list],
    status_code=status.HTTP_200_OK,
    summary="Analyze conflicts between rules and existing active rules",
)
async def analyze_rule_conflicts(
    payload: AnalyzeConflictsRequest,
    session: AsyncSession = Depends(get_db),
):
    conflicts = await _conflict_analyzer.analyze_conflicts(
        session=session,
        kind="RULE",
        definition=payload.definition,
        meta=payload.meta,
    )
    return success(data=conflicts, message="Rule conflicts analyzed successfully")
