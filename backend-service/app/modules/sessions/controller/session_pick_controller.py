import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import async_session_factory, get_db
from app.core.exception.app_exceptions import NotFoundException
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.sessions.engine import session_loop_runner
from app.modules.sessions.schema.session_pick_schema import (
    SessionPickResponse,
    SessionPickSearchFilter,
)
from app.modules.sessions.service.session_loop_service import session_loop_service

session_pick_router = APIRouter(prefix="/sessions", tags=["Trading Session Loop"])

_loop_service = session_loop_service


HEARTBEAT_SECONDS = 10


async def _loop_events(session_id: int) -> AsyncGenerator[str, None]:
    """SSE: the server loop's newest state on connect, then one `loop` event per change. `heartbeat` events carry
    serverTime so the client keeps its clock offset fresh; `closed` is the last event when the loop has ended."""
    q = session_loop_runner.subscribe(session_id)
    try:
        first = session_loop_runner.snapshot(session_id)
        if first is not None:
            yield f"event: loop\ndata: {first.model_dump_json()}\n\n"
        elif not session_loop_runner.is_running(session_id):
            yield "event: closed\ndata: {}\n\n"
            return
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                if not session_loop_runner.is_running(session_id):
                    yield "event: closed\ndata: {}\n\n"
                    return
                now = datetime.now(UTC).isoformat()
                yield f'event: heartbeat\ndata: {{"serverTime": "{now}"}}\n\n'
                continue
            if item is None:
                yield "event: closed\ndata: {}\n\n"
                return
            yield f"event: loop\ndata: {item.model_dump_json()}\n\n"
    finally:
        session_loop_runner.unsubscribe(session_id, q)


@session_pick_router.get("/{id}/stream", summary="Live loop updates (SSE) for a session")
async def stream_session_loop(id: int):
    """Server-sent events: pushes the session loop's state whenever it changes (new pick, pick expired/locked,
    capital moved, scan result). Nothing is computed here -- the server-side loop does the work."""
    async with async_session_factory() as db:  # short-lived: never held open for the life of the stream
        exists = await _loop_service.sessions.get_by_id(db, id) is not None
    if not exists:
        raise NotFoundException(message=f"Trading session {id} not found")
    return StreamingResponse(
        _loop_events(id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@session_pick_router.post(
    "/{id}/picks/{pick_id}/lock",
    response_model=ApiResponse[SessionPickResponse],
    status_code=status.HTTP_200_OK,
    summary="Trade Lock a pick",
)
async def lock_pick(id: int, pick_id: int, session: AsyncSession = Depends(get_db)):
    """Locks the pick while it is still OFFERED and its opportunity has not expired (409 otherwise) and returns the item's current price
    as lockedPrice. Places no order."""
    result = await _loop_service.lock(session, id, pick_id)
    return success(data=result, message="Trade locked")


@session_pick_router.post(
    "/{id}/picks/search",
    response_model=ApiResponse[PageResult[SessionPickResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search a session's picks",
)
async def search_picks(id: int, filter_obj: SessionPickSearchFilter, session: AsyncSession = Depends(get_db)):
    """Paged history of the picks offered in a session, filterable by pickState."""
    page = await _loop_service.search_picks(session, id, filter_obj)
    return success(data=page, message="Session picks fetched successfully")
