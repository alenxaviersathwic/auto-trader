import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import async_session_factory, get_db
from app.core.exception.app_exceptions import NotFoundException
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import created, success
from app.modules.trades.engine.trade_pilot_runner import trade_pilot_runner
from app.modules.trades.schema.trade_schema import (
    LotSuggestionResponse,
    TradeAdjustRequest,
    TradeCreateRequest,
    TradeExitRequest,
    TradeLiveSnapshot,
    TradeResponse,
    TraderPresetResponse,
    TradeSearchFilter,
)
from app.modules.trades.service.trade_service import trade_service

trade_router = APIRouter(prefix="/trades", tags=["Active Trader"])
HEARTBEAT_SECONDS = 10


async def _trade_events(trade_id: int) -> AsyncGenerator[str, None]:
    """SSE stream for one active trade: sends initial snapshot on connect, then pushes every change."""
    q = trade_pilot_runner.subscribe(trade_id)
    try:
        first = trade_pilot_runner.snapshot(trade_id)
        if first is None:
            async with async_session_factory() as db:
                t_resp = await trade_service.get_by_id(db, trade_id)
            first = TradeLiveSnapshot(tradeId=trade_id, serverTime=datetime.now(UTC), trade=t_resp)
        yield f"event: trade\ndata: {first.model_dump_json()}\n\n"
        if first.trade.tradeState != "RUNNING" and not trade_pilot_runner.is_running(trade_id):
            yield "event: closed\ndata: {}\n\n"
            return

        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                if not trade_pilot_runner.is_running(trade_id):
                    yield "event: closed\ndata: {}\n\n"
                    return
                now = datetime.now(UTC).isoformat()
                yield f'event: heartbeat\ndata: {{"serverTime": "{now}"}}\n\n'
                continue
            if item is None:
                yield "event: closed\ndata: {}\n\n"
                return
            yield f"event: trade\ndata: {item.model_dump_json()}\n\n"
    finally:
        trade_pilot_runner.unsubscribe(trade_id, q)


@trade_router.get(
    "/presets",
    response_model=ApiResponse[list[TraderPresetResponse]],
    status_code=status.HTTP_200_OK,
    summary="List the 3 institutional preset Traders with live and historical stats",
)
async def list_trader_presets(
    session: AsyncSession = Depends(get_db),
):
    result = await trade_service.list_presets(session)
    return success(data=result, message="Trader presets fetched successfully")


@trade_router.get(
    "/preview-sizing",
    response_model=ApiResponse[LotSuggestionResponse],
    status_code=status.HTTP_200_OK,
    summary="Preview suggested lots based on entryAt, capital, and risk budget",
)
async def preview_sizing(
    sessionId: int = Query(..., gt=0),
    pickId: int = Query(..., gt=0),
    entryAt: Optional[float] = Query(default=None, gt=0),
    session: AsyncSession = Depends(get_db),
):
    result = await trade_service.preview_sizing(session, sessionId, pickId, entryAt)
    return success(data=result, message="Lot sizing preview computed successfully")


@trade_router.post(
    "",
    response_model=ApiResponse[TradeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Enter a locked pick and start its dedicated Trader loop",
)
async def create_trade(
    payload: TradeCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    result = await trade_service.enter_trade(session, payload)
    return created(data=result, message="Trade entered and Trader pilot started")


@trade_router.post(
    "/search",
    response_model=ApiResponse[PageResult[TradeResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search active and historical trades",
)
async def search_trades(
    filter_obj: TradeSearchFilter,
    session: AsyncSession = Depends(get_db),
):
    page = await trade_service.search(session, filter_obj)
    return success(data=page, message="Trades fetched successfully")


@trade_router.get(
    "/{id}",
    response_model=ApiResponse[TradeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get a trade by id with latest 1m candles and trail history",
)
async def get_trade(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    result = await trade_service.get_by_id(session, id)
    return success(data=result, message="Trade retrieved successfully")


@trade_router.get("/{id}/stream", summary="Live SSE stream for a single trade")
async def stream_trade(id: int):
    async with async_session_factory() as db:
        exists = await trade_service.repo.get_by_id(db, id) is not None
    if not exists:
        raise NotFoundException(message=f"Trade {id} not found")
    return StreamingResponse(
        _trade_events(id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@trade_router.post(
    "/{id}/adjust",
    response_model=ApiResponse[TradeResponse],
    status_code=status.HTTP_200_OK,
    summary="Manually adjust current Stop-Loss and/or Target on a running trade",
)
async def adjust_trade(
    id: int,
    payload: TradeAdjustRequest,
    session: AsyncSession = Depends(get_db),
):
    result = await trade_service.adjust_levels(session, id, payload)
    return success(data=result, message="Trade levels updated")


@trade_router.post(
    "/{id}/exit",
    response_model=ApiResponse[TradeResponse],
    status_code=status.HTTP_200_OK,
    summary="Manually square off / exit a running trade",
)
async def exit_trade(
    id: int,
    payload: TradeExitRequest,
    session: AsyncSession = Depends(get_db),
):
    result = await trade_service.manual_exit(session, id, payload)
    return success(data=result, message="Trade squared off")

