import contextvars
import uuid
from typing import Optional

_flow_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("flow_id", default=None)


class LogFlowContext:
    """
    Context manager and holder for request-scoped correlation flow IDs.
    Matches trading-engine's LogFlowContext pattern.
    """

    @staticmethod
    def generate_flow_id() -> str:
        """Generates an 8-character lowercase alphanumeric flow identifier."""
        return uuid.uuid4().hex[:8]

    @classmethod
    def start(cls, flow_id: Optional[str] = None) -> str:
        """Starts a flow context with an optional explicit flow ID or generates a new one."""
        if flow_id and flow_id.strip():
            fid = flow_id.strip()
        else:
            fid = cls.generate_flow_id()
        _flow_id_ctx.set(fid)
        return fid

    @classmethod
    def set_flow_id(cls, flow_id: str) -> None:
        """Sets the active flow ID."""
        cls.start(flow_id)

    @classmethod
    def get_flow_id(cls) -> str:
        """Retrieves the active flow ID or empty string if none is active."""
        return _flow_id_ctx.get() or ""

    @classmethod
    def current(cls) -> str:
        """Alias for get_flow_id() matching LogFlowContext.current()."""
        return cls.get_flow_id()

    @classmethod
    def clear(cls) -> None:
        """Clears the active flow context."""
        _flow_id_ctx.set(None)
