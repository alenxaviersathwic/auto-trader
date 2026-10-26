from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.core.exception.app_exceptions import AppException
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.system.schema.system_schema import (
    EngineRunRequest,
    EngineSearchFilter,
    EngineSummary,
    SystemStatusResponse,
)
from app.modules.system.service.engine_registry import engine_registry
from app.modules.system.service.status_service import StatusService

system_router = APIRouter(prefix="/system", tags=["System"])


@system_router.get(
    "/status",
    response_model=ApiResponse[SystemStatusResponse],
    status_code=status.HTTP_200_OK,
)
async def get_system_status(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemStatusResponse]:
    """Retrieve health and connectivity status of all core components."""
    res = await StatusService.check_all(session)
    return success(data=res, message="System status fetched successfully")


@system_router.post(
    "/status/refresh",
    response_model=ApiResponse[SystemStatusResponse],
    status_code=status.HTTP_200_OK,
)
async def refresh_system_status(
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SystemStatusResponse]:
    """Force re-check health of all system components."""
    res = await StatusService.check_all(session)
    return success(data=res, message="System status refreshed successfully")


@system_router.post(
    "/engines/search",
    response_model=ApiResponse[PageResult[EngineSummary]],
    status_code=status.HTTP_200_OK,
)
async def search_engines(
    filter_body: EngineSearchFilter,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[PageResult[EngineSummary]]:
    """List registered execution engines matching the filter."""
    engines = engine_registry.get_all()
    summaries: List[EngineSummary] = []

    for eng in engines:
        # Check current state from engine
        try:
            state_info = await eng.current_state(session)
        except Exception:
            state_info = {"state": "IDLE"}

        summary = EngineSummary(
            code=eng.code,
            name=eng.name,
            description=eng.description,
            module=eng.module,
            runnable=eng.runnable,
            currentState=state_info.get("state", "IDLE"),
            lastRunSummary=state_info.get("lastRunSummary"),
            lastRunAt=state_info.get("lastRunAt"),
            storedInfo=state_info.get("storedInfo"),
            stats=state_info.get("stats"),
            paramSchema=eng.paramSchema,
        )
        summaries.append(summary)

    # Filter by query if present
    if filter_body.query:
        q = filter_body.query.lower()
        summaries = [
            s for s in summaries if q in s.code.lower() or q in s.name.lower() or q in s.description.lower()
        ]

    total_items = len(summaries)
    page = filter_body.page
    limit = filter_body.limit
    start_idx = page * limit
    end_idx = start_idx + limit
    page_items = summaries[start_idx:end_idx]
    total_pages = (total_items + limit - 1) // limit if limit > 0 else 0

    page_result = PageResult(
        list=page_items,
        page=page,
        limit=limit,
        totalPages=total_pages,
        totalItems=total_items,
    )
    return success(data=page_result, message="Engines retrieved successfully")


@system_router.get(
    "/engines/{code}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def get_engine_detail(
    code: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Get details and recent runs of an execution engine."""
    eng = engine_registry.get(code)
    if not eng:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Engine '{code}' is not registered",
        )

    current_state = await eng.current_state(session)
    recent_runs = await eng.last_runs(5, session)

    data = {
        "code": eng.code,
        "name": eng.name,
        "description": eng.description,
        "module": eng.module,
        "runnable": eng.runnable,
        "paramSchema": eng.paramSchema,
        "currentState": current_state,
        "recentRuns": recent_runs,
    }
    return success(data=data, message="Engine details fetched successfully")


@system_router.post(
    "/engines/{code}/run",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_engine(
    code: str,
    body: EngineRunRequest,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Trigger an execution engine run."""
    eng = engine_registry.get(code)
    if not eng:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Engine '{code}' is not registered",
        )
    if not eng.runnable:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=f"Engine '{code}' is not runnable",
        )

    params = body.model_dump(exclude_unset=True)
    res = await eng.start(params, session)
    return success(data=res, message=f"Engine '{code}' started successfully", status_code=status.HTTP_202_ACCEPTED)


@system_router.post(
    "/engines/{code}/cancel",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def cancel_engine(
    code: str,
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[Dict[str, Any]]:
    """Cancel currently executing job of an engine."""
    eng = engine_registry.get(code)
    if not eng:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"Engine '{code}' is not registered",
        )

    res = await eng.cancel(session)
    return success(data=res, message=f"Engine '{code}' cancellation requested")
