from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class Engine(Protocol):
    code: str
    name: str
    description: str
    module: str
    runnable: bool
    paramSchema: Dict[str, Any]

    async def start(self, params: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        """Start the engine with provided params."""
        ...

    async def cancel(self, session: AsyncSession) -> Dict[str, Any]:
        """Cancel any running job for this engine."""
        ...

    async def current_state(self, session: AsyncSession) -> Dict[str, Any]:
        """Return the current runtime state and brief stats of the engine."""
        ...

    async def last_runs(self, n: int, session: AsyncSession) -> List[Dict[str, Any]]:
        """Return the last n runs."""
        ...


class EngineRegistry:
    """Central decoupled registry for all execution engines."""

    def __init__(self):
        self._engines: Dict[str, Engine] = {}

    def register(self, engine: Engine) -> None:
        self._engines[engine.code] = engine

    def unregister(self, code: str) -> None:
        self._engines.pop(code, None)

    def get(self, code: str) -> Optional[Engine]:
        return self._engines.get(code)

    def get_all(self) -> List[Engine]:
        return list(self._engines.values())


engine_registry = EngineRegistry()
