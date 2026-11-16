"""
notify(): how any module raises a user notification, through the event bus (core/events/event_bus.py), so the
producer never imports the notifications module. The notifications module subscribes to NOTIFICATION_EVENT and fans
the event out to every open browser (SSE), where the user's settings decide what is shown.

Never raises: a notification must not break a trade, a lock or a loop tick.
"""
import logging
from typing import Any

from app.core.events.event_bus import event_bus

NOTIFICATION_EVENT = "notification"
logger = logging.getLogger("auto-trader.notify")

# kind -> what the user can switch on and off in Settings > Notifications
NEW_SUGGESTION = "NEW_SUGGESTION"
TRADE_LOCKED = "TRADE_LOCKED"
TRADE_ENTERED = "TRADE_ENTERED"
EXIT_SIGNAL = "EXIT_SIGNAL"
TRADE_EXITED = "TRADE_EXITED"
SESSION_HALTED = "SESSION_HALTED"
LEARNING = "LEARNING"
RESEARCH = "RESEARCH"


async def notify(kind: str, title: str, body: str, *, severity: str = "info", session_id: int | None = None,
                 trade_id: int | None = None, link: str | None = None, data: dict[str, Any] | None = None) -> None:
    """severity: info | success | warning | danger. link: a frontend route to open on click."""
    try:
        await event_bus.publish(NOTIFICATION_EVENT, {
            "kind": kind, "title": title, "body": body, "severity": severity, "sessionId": session_id,
            "tradeId": trade_id, "link": link, "data": data or {},
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"notification dropped ({kind}): {type(e).__name__}: {e}")
