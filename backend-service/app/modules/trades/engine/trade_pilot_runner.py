import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import NotFoundException
from app.core.logging.logger import logger
from app.modules.trades.schema.trade_schema import TradeLiveSnapshot
from app.modules.trades.service.trade_service import TradeService, trade_service

_IST = ZoneInfo("Asia/Kolkata")
TICK_SECONDS = 1.0
ERROR_BACKOFF_SECONDS = 3.0


class TradePilotRunner:
    """
    Independent server-side Trader loop: one `asyncio.Task` per active `tradeId` (`trade-pilot-{id}`).
    Ticks every 1 second, updates SL / Target / telemetry / exit state via `TradeService.tick()`,
    caches the latest `TradeLiveSnapshot`, and streams updates over SSE (`/api/v1/trades/{id}/stream`).
    """

    def __init__(
        self,
        service: TradeService | None = None,
        session_factory: Callable = async_session_factory,
        tick_seconds: float = TICK_SECONDS,
    ):
        self.service = service or trade_service
        self._factory = session_factory
        self._tick_seconds = tick_seconds
        self._tasks: dict[int, asyncio.Task] = {}
        self._snapshots: dict[int, TradeLiveSnapshot] = {}
        self._keys: dict[int, str] = {}
        self._subs: dict[int, set[asyncio.Queue]] = {}

    def is_running(self, trade_id: int) -> bool:
        t = self._tasks.get(trade_id)
        return t is not None and not t.done()

    def start(self, trade_id: int) -> None:
        if self.is_running(trade_id):
            return
        self._tasks[trade_id] = asyncio.create_task(self._run(trade_id), name=f"trade-pilot-{trade_id}")
        logger.info(f"trade pilot loop started: trade={trade_id}")

    def stop(self, trade_id: int) -> None:
        t = self._tasks.pop(trade_id, None)
        if t and not t.done():
            t.cancel()
            logger.info(f"trade pilot loop stopped: trade={trade_id}")
        self._close_subscribers(trade_id)

    async def resume_today(self) -> int:
        """Startup: resume the pilot loop for every RUNNING trade entered today (IST)."""
        now_ist = datetime.now(UTC).astimezone(_IST)
        day_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        async with self._factory() as db:
            ids = await self.service.repo.running_ids_today(db, day_start)
        for tid in ids:
            self.start(tid)
        return len(ids)

    async def stop_all(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._snapshots.clear()
        for tid in list(self._subs):
            self._close_subscribers(tid)

    def snapshot(self, trade_id: int) -> TradeLiveSnapshot | None:
        snap = self._snapshots.get(trade_id)
        if snap is None:
            return None
        return snap.model_copy(update={"serverTime": datetime.now(UTC)})

    def publish_snapshot(self, trade_id: int, snap: TradeLiveSnapshot) -> None:
        self._snapshots[trade_id] = snap
        self._publish(trade_id, snap)

    # ───────────────────────── SSE pub/sub ─────────────────────────
    def subscribe(self, trade_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=16)
        self._subs.setdefault(trade_id, set()).add(q)
        return q

    def unsubscribe(self, trade_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(trade_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(trade_id, None)

    @staticmethod
    def _put(q: asyncio.Queue, item: TradeLiveSnapshot | None) -> None:
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(item)

    def _close_subscribers(self, trade_id: int) -> None:
        for q in list(self._subs.get(trade_id, ())):
            self._put(q, None)

    @staticmethod
    def _change_key(snap: TradeLiveSnapshot) -> str:
        d = snap.model_dump(mode="json", exclude={"serverTime"})
        return json.dumps(d, sort_keys=True, default=str)

    def _publish(self, trade_id: int, snap: TradeLiveSnapshot) -> None:
        key = self._change_key(snap)
        if self._keys.get(trade_id) == key:
            return
        self._keys[trade_id] = key
        fresh = self.snapshot(trade_id)
        for q in list(self._subs.get(trade_id, ())):
            self._put(q, fresh)

    # ───────────────────────── loop worker ─────────────────────────
    async def _run(self, trade_id: int) -> None:
        try:
            while True:
                delay = self._tick_seconds
                try:
                    async with self._factory() as db:
                        snap = await self.service.tick(db, trade_id)
                        await db.commit()
                    self._snapshots[trade_id] = snap
                    self._publish(trade_id, snap)
                    if snap.trade.tradeState != "RUNNING":
                        return
                except NotFoundException:
                    self._snapshots.pop(trade_id, None)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001
                    logger.error(f"trade pilot tick failed: trade={trade_id} {type(e).__name__}: {e}")
                    delay = ERROR_BACKOFF_SECONDS
                await asyncio.sleep(delay)
        finally:
            if self._tasks.get(trade_id) is asyncio.current_task():
                self._tasks.pop(trade_id, None)
                self._close_subscribers(trade_id)


trade_pilot_runner = TradePilotRunner()

