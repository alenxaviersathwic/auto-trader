"""
Notification hub: keeps the last MAX_KEPT notifications in memory and pushes each new one to every open stream.

One uvicorn worker, so in-memory is the whole picture. Notifications are not stored in the database: they are a live
signal, and every one of them points at something that is stored (a session, a pick, a trade, an autopsy).
"""
import asyncio
import math
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.core.events.event_bus import event_bus
from app.core.events.notify import NOTIFICATION_EVENT
from app.core.pagination.page_result import PageResult
from app.modules.notifications.schema.notification_schema import NotificationResponse, NotificationSearchFilter

MAX_KEPT = 300
QUEUE_SIZE = 200


class NotificationHub:
    def __init__(self) -> None:
        self._kept: deque[NotificationResponse] = deque(maxlen=MAX_KEPT)
        self._queues: set[asyncio.Queue[NotificationResponse]] = set()
        self._next_id = 1
        self._registered = False

    def register(self) -> None:
        """Subscribe to the event bus once (called from the app lifespan)."""
        if not self._registered:
            event_bus.subscribe(NOTIFICATION_EVENT, self._on_event)
            self._registered = True

    async def _on_event(self, payload: dict[str, Any]) -> None:
        self.publish(payload)

    def publish(self, payload: dict[str, Any]) -> NotificationResponse:
        n = NotificationResponse(id=self._next_id, createdAt=datetime.now(UTC), **payload)
        self._next_id += 1
        self._kept.append(n)
        for q in list(self._queues):
            if q.full():  # a stalled browser never blocks the producers: drop its oldest
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(n)
        return n

    def subscribe(self) -> asyncio.Queue[NotificationResponse]:
        q: asyncio.Queue[NotificationResponse] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[NotificationResponse]) -> None:
        self._queues.discard(q)

    def since(self, after_id: int) -> list[NotificationResponse]:
        return [n for n in self._kept if n.id > after_id]

    def search(self, f: NotificationSearchFilter) -> PageResult[NotificationResponse]:
        rows = [n for n in self._kept
                if (f.kind is None or n.kind == f.kind.upper())
                and (f.sessionId is None or n.sessionId == f.sessionId)
                and (f.afterId is None or n.id > f.afterId)]
        if (f.sortDir or "desc").lower() == "desc":
            rows.reverse()
        total = len(rows)
        return PageResult(list=rows[f.page * f.limit:(f.page + 1) * f.limit], page=f.page, limit=f.limit,
                          totalPages=math.ceil(total / f.limit) if total else 0, totalItems=total)


notification_hub = NotificationHub()
