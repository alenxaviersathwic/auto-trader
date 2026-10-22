from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import created, success
from app.modules.strategies.schema.import_schema import ExportRequest, ExportResponse, ImportBatchResponse, ImportRequest
from app.modules.strategies.schema.performance_schema import (
    HealthOverrideRequest,
    HealthResponse,
    PerformanceSnapshotCreate,
    PerformanceSnapshotFilter,
    PerformanceSnapshotResponse,
    RecomputeHealthResponse,
)
from app.modules.strategies.schema.strategy_schema import (
    EvaluateStrategyRequest,
    EvaluateStrategyResponse,
    RequirementsResponse,
    StrategyCreate,
    StrategyDetailResponse,
    StrategyEnabledUpdate,
    StrategyFilter,
    StrategyLifecycleUpdate,
    StrategyResponse,
    StrategyUpdate,
    StrategyVersionFilter,
    StrategyVersionResponse,
    ValidateDefinitionRequest,
    ValidateDefinitionResponse,
)
from app.modules.strategies.service.health_service import HealthService
from app.modules.strategies.service.import_export_service import ImportExportService
from app.modules.strategies.service.seed_service import SeedService
from app.modules.strategies.service.strategy_service import StrategyService

strategy_router = APIRouter(prefix="/strategies", tags=["Strategies"])

_strategy_service = StrategyService()
_health_service = HealthService()
_seed_service = SeedService()
_import_export_service = ImportExportService()


@strategy_router.post(
    "/search",
    response_model=ApiResponse[PageResult[StrategyResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search strategies with pagination and filters",
)
async def search_strategies(
    filter_obj: StrategyFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _strategy_service.search(session, filter_obj)
    return success(data=page_res, message="Strategies retrieved successfully")


@strategy_router.post(
    "",
    response_model=ApiResponse[StrategyDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new strategy with initial version",
)
async def create_strategy(
    payload: StrategyCreate,
    session: AsyncSession = Depends(get_db),
):
    created_strat = await _strategy_service.create(session, payload)
    return created(data=created_strat, message="Strategy created successfully")


@strategy_router.post(
    "/validate",
    response_model=ApiResponse[ValidateDefinitionResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate strategy definition against registry catalog",
)
async def validate_definition(
    payload: ValidateDefinitionRequest,
    session: AsyncSession = Depends(get_db),
):
    val_res = await _strategy_service.validate_definition(session, payload)
    return success(data=val_res, message="Strategy definition validated")


@strategy_router.post(
    "/evaluate",
    response_model=ApiResponse[EvaluateStrategyResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate strategy conditions and adjustments against context",
)
async def evaluate_strategy(
    payload: EvaluateStrategyRequest,
    session: AsyncSession = Depends(get_db),
):
    eval_res = await _strategy_service.evaluate(session, payload)
    return success(data=eval_res, message="Strategy evaluation executed")


@strategy_router.post(
    "/seed-defaults",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Seed registries, default health policy, textbook and legacy strategies",
)
async def seed_defaults(
    session: AsyncSession = Depends(get_db),
):
    res = await _seed_service.seed_defaults(session)
    return success(data=res, message="Default catalogs and strategies seeded successfully")


@strategy_router.post(
    "/import",
    response_model=ApiResponse[ImportBatchResponse],
    status_code=status.HTTP_200_OK,
    summary="Import strategy bundle (BUNDLE_V2 or LEGACY_ALGO_V1)",
)
async def import_strategies(
    payload: ImportRequest,
    session: AsyncSession = Depends(get_db),
):
    batch_res = await _import_export_service.import_bundle(session, payload)
    return success(data=batch_res, message="Import batch processed")


@strategy_router.post(
    "/export",
    response_model=ApiResponse[ExportResponse],
    status_code=status.HTTP_200_OK,
    summary="Export active strategies and rules as V2 bundle",
)
async def export_strategies(
    payload: ExportRequest,
    session: AsyncSession = Depends(get_db),
):
    exp_res = await _import_export_service.export_bundle(session, payload)
    return success(data=exp_res, message="Export generated successfully")


@strategy_router.post(
    "/health/recompute",
    response_model=ApiResponse[RecomputeHealthResponse],
    status_code=status.HTTP_200_OK,
    summary="Recompute health across all active strategies against policies",
)
async def recompute_health_all(
    session: AsyncSession = Depends(get_db),
):
    res = await _health_service.recompute_all(session)
    return success(data=res, message=f"Health recomputed for {res.recomputedCount} strategies")


@strategy_router.get(
    "/{id}",
    response_model=ApiResponse[StrategyDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get single strategy with current version and performance snapshot",
)
async def get_strategy_by_id(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    strat = await _strategy_service.get_by_id(session, id)
    return success(data=strat, message="Strategy retrieved successfully")


@strategy_router.put(
    "/{id}",
    response_model=ApiResponse[StrategyDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Update strategy metadata or definition (creates new version if changed)",
)
async def update_strategy(
    id: int,
    payload: StrategyUpdate,
    session: AsyncSession = Depends(get_db),
):
    updated = await _strategy_service.update(session, id, payload)
    return success(data=updated, message="Strategy updated successfully")


@strategy_router.delete(
    "/{id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Soft delete strategy",
)
async def delete_strategy(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    await _strategy_service.delete(session, id)
    return success(data={"id": id, "deleted": True}, message="Strategy deleted successfully")


@strategy_router.post(
    "/{id}/clone",
    response_model=ApiResponse[StrategyDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Clone strategy as new DRAFT",
)
async def clone_strategy(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    cloned = await _strategy_service.clone(session, id)
    return created(data=cloned, message="Strategy cloned successfully")


@strategy_router.patch(
    "/{id}/enabled",
    response_model=ApiResponse[StrategyResponse],
    status_code=status.HTTP_200_OK,
    summary="Toggle strategy enabled state",
)
async def set_strategy_enabled(
    id: int,
    payload: StrategyEnabledUpdate,
    session: AsyncSession = Depends(get_db),
):
    res = await _strategy_service.set_enabled(session, id, payload)
    return success(data=res, message="Strategy enabled status updated")


@strategy_router.patch(
    "/{id}/lifecycle",
    response_model=ApiResponse[StrategyResponse],
    status_code=status.HTTP_200_OK,
    summary="Update strategy lifecycle state",
)
async def update_strategy_lifecycle(
    id: int,
    payload: StrategyLifecycleUpdate,
    session: AsyncSession = Depends(get_db),
):
    res = await _strategy_service.update_lifecycle(session, id, payload)
    return success(data=res, message="Strategy lifecycle state updated")


@strategy_router.post(
    "/{id}/versions/search",
    response_model=ApiResponse[PageResult[StrategyVersionResponse]],
    status_code=status.HTTP_200_OK,
    summary="List strategy version history",
)
async def list_strategy_versions(
    id: int,
    payload: StrategyVersionFilter,
    session: AsyncSession = Depends(get_db),
):
    versions_page = await _strategy_service.list_versions(session, id, payload)
    return success(data=versions_page, message="Strategy versions retrieved")


@strategy_router.get(
    "/{id}/versions/{versionNo}",
    response_model=ApiResponse[StrategyVersionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get specific version for strategy",
)
async def get_strategy_version(
    id: int,
    versionNo: int,
    session: AsyncSession = Depends(get_db),
):
    v = await _strategy_service.get_version(session, id, versionNo)
    return success(data=v, message="Strategy version retrieved")


@strategy_router.post(
    "/{id}/versions/{versionNo}/activate",
    response_model=ApiResponse[StrategyResponse],
    status_code=status.HTTP_200_OK,
    summary="Activate specific version as current active definition",
)
async def activate_strategy_version(
    id: int,
    versionNo: int,
    session: AsyncSession = Depends(get_db),
):
    res = await _strategy_service.activate_version(session, id, versionNo)
    return success(data=res, message=f"Version {versionNo} activated successfully")


@strategy_router.get(
    "/{id}/versions/{versionNo}/requirements",
    response_model=ApiResponse[RequirementsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get operand and data requirements for version",
)
async def get_strategy_version_requirements(
    id: int,
    versionNo: int,
    session: AsyncSession = Depends(get_db),
):
    reqs = await _strategy_service.get_requirements(session, id, versionNo)
    return success(data=reqs, message="Requirements extracted successfully")


@strategy_router.post(
    "/{id}/performance/search",
    response_model=ApiResponse[PageResult[PerformanceSnapshotResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search performance snapshots for strategy",
)
async def search_strategy_performance(
    id: int,
    payload: PerformanceSnapshotFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _strategy_service.search_performance(session, id, payload)
    return success(data=page_res, message="Performance snapshots retrieved")


@strategy_router.post(
    "/{id}/performance",
    response_model=ApiResponse[PerformanceSnapshotResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add new performance snapshot for strategy",
)
async def add_strategy_performance(
    id: int,
    payload: PerformanceSnapshotCreate,
    session: AsyncSession = Depends(get_db),
):
    snap = await _strategy_service.add_performance_snapshot(session, id, payload)
    return created(data=snap, message="Performance snapshot saved and health evaluated")


@strategy_router.get(
    "/{id}/health",
    response_model=ApiResponse[HealthResponse],
    status_code=status.HTTP_200_OK,
    summary="Get effective strategy health, policy, and transition events",
)
async def get_strategy_health(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    health_res = await _health_service.get_strategy_health(session, id)
    return success(data=health_res, message="Strategy health details retrieved")


@strategy_router.post(
    "/{id}/health/override",
    response_model=ApiResponse[HealthResponse],
    status_code=status.HTTP_200_OK,
    summary="Manually override strategy health",
)
async def override_strategy_health(
    id: int,
    payload: HealthOverrideRequest,
    session: AsyncSession = Depends(get_db),
):
    health_res = await _health_service.override_health(session, id, payload)
    return success(data=health_res, message="Strategy health overridden successfully")
