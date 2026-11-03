from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import created, success
from app.modules.sessions.schema.trading_session_schema import (
    TradingSessionCreateRequest,
    TradingSessionResponse,
    TradingSessionSearchFilter,
    TradingSessionUpdateRequest,
)
from app.modules.sessions.service.trading_session_service import TradingSessionService

session_router = APIRouter(prefix="/sessions", tags=["Trading Sessions"])

_session_service = TradingSessionService()


@session_router.post(
    "",
    response_model=ApiResponse[TradingSessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a trading session",
)
async def create_session(
    payload: TradingSessionCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Creates a trading session: the capital/risk/scope/automation envelope for a trading day."""
    result = await _session_service.create(session, payload)
    return created(data=result, message="Trading session created successfully")


@session_router.post(
    "/search",
    response_model=ApiResponse[PageResult[TradingSessionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search trading sessions with pagination and filters",
)
async def search_sessions(
    filter_obj: TradingSessionSearchFilter,
    session: AsyncSession = Depends(get_db),
):
    """Paged listing of trading sessions, filterable by scope, sessionStatus, sessionType, userId, tradeDate."""
    page_result = await _session_service.search(session, filter_obj)
    return success(data=page_result, message="Trading sessions fetched successfully")


@session_router.get(
    "/{id}",
    response_model=ApiResponse[TradingSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a trading session by id",
)
async def get_session(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves a single trading session by id."""
    result = await _session_service.get_by_id(session, id)
    return success(data=result, message="Trading session retrieved successfully")


@session_router.put(
    "/{id}",
    response_model=ApiResponse[TradingSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Update a trading session",
)
async def update_session(
    id: int,
    payload: TradingSessionUpdateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Updates only the fields provided (e.g. closing a session via sessionStatus=CLOSED)."""
    result = await _session_service.update(session, id, payload)
    return success(data=result, message="Trading session updated successfully")


@session_router.delete(
    "/{id}",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Soft delete a trading session",
)
async def delete_session(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """Soft deletes a trading session."""
    await _session_service.delete(session, id)
    return success(data={"id": id, "deleted": True}, message="Trading session deleted successfully")
