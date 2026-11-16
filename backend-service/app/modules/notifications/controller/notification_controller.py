import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header, Query, status
from fastapi.responses import StreamingResponse

from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import success
from app.modules.notifications.schema.notification_schema import NotificationResponse, NotificationSearchFilter
from app.modules.notifications.service.notification_hub import notification_hub

notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])
HEARTBEAT_SECONDS = 20


async def _events(after_id: int | None) -> AsyncGenerator[str, None]:
    """SSE: when `after_id` is given, everything newer than it first (a reconnect misses nothing still kept), then
    one `notification` event per new notification, and a `heartbeat` every HEARTBEAT_SECONDS so proxies keep the
    stream open. Without `after_id` only new notifications are sent."""
    q = notification_hub.subscribe()
    try:
        for n in notification_hub.since(after_id) if after_id is not None else []:
            yield f"id: {n.id}\nevent: notification\ndata: {n.model_dump_json()}\n\n"
        while True:
            try:
                n = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_SECONDS)
                yield f"id: {n.id}\nevent: notification\ndata: {n.model_dump_json()}\n\n"
            except TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"
    finally:
        notification_hub.unsubscribe(q)


@notification_router.get("/stream", summary="Live notifications (Server-Sent Events)")
async def stream_notifications(
    afterId: int | None = Query(default=None, ge=0, description="Replay notifications newer than this id"),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """The browser's EventSource sends Last-Event-ID on every automatic reconnect: that wins over the query."""
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else afterId
    return StreamingResponse(_events(after), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@notification_router.post("/search", response_model=ApiResponse[PageResult[NotificationResponse]],
                          status_code=status.HTTP_200_OK, summary="Recent notifications (kept in memory)")
async def search_notifications(filter_obj: NotificationSearchFilter):
    return success(data=notification_hub.search(filter_obj), message="Notifications fetched")
