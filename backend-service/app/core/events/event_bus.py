import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger("auto-trader.event_bus")

EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    """
    In-memory async event bus for decoupled inter-module communication.
    Modules subscribe to event types and publish events asynchronously.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribes an async handler to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler {handler.__name__} to event '{event_type}'")

    async def publish(self, event_type: str, payload: Any = None) -> None:
        """Publishes an event to all registered subscribers concurrently."""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        logger.debug(
            f"Publishing event '{event_type}' to {len(handlers)} handler(s)"
        )
        tasks = [self._safe_invoke(handler, event_type, payload) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_invoke(
        self, handler: EventHandler, event_type: str, payload: Any
    ) -> None:
        try:
            await handler(payload)
        except Exception:
            logger.exception(
                f"Error in event handler {handler.__name__} for event '{event_type}'"
            )


# Global singleton event bus
event_bus = EventBus()
