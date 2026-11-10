import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.db.entity_status import EntityStatus
from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import NotFoundException
from app.core.logging.logger import logger
from app.modules.sessions.entity.trading_session_entity import TradingSession
from app.modules.sessions.schema.session_pick_schema import SessionLoopResponse
from app.modules.sessions.service.session_loop_service import SessionLoopService, session_loop_service

_IST = ZoneInfo("Asia/Kolkata")

TICK_SECONDS = 1.0       # every second counts in trading
ERROR_BACKOFF_SECONDS = 3.0
STOP_STATES = {"SESSION_CLOSED", "UNSUPPORTED_TYPE"}  # nothing a later tick could change


class SessionLoopRunner:
    """
    Server-side loop: one background task per eligible session, started by the create-session API (and resumed
    on startup), ticking every second. No HTTP route drives it. The newest tick result is kept in memory and
    served through GET /sessions/{id}. Single uvicorn worker, so in-process state is enough.
    """

    def __init__(
        self,
        service: SessionLoopService | None = None,
        session_factory: Callable = async_session_factory,
        tick_seconds: float = TICK_SECONDS,
    ):
        self.service = service or session_loop_service
        self._factory = session_factory
        self._tick_seconds = tick_seconds
        self._tasks: dict[int, asyncio.Task] = {}
        self._snapshots: dict[int, SessionLoopResponse] = {}
        self._keys: dict[int, str] = {}
        self._subs: dict[int, set[asyncio.Queue]] = {}

    # ───────────────────────── control ─────────────────────────
    @staticmethod
    def eligible(s: TradingSession, now: datetime | None = None) -> bool:
        today = (now or datetime.now(UTC)).astimezone(_IST).date().isoformat()
        return (
            s.sessionStatus == "ACTIVE" and s.sessionType in ("MANUAL", "SEMI_AUTO", "FULL_AUTO")
            and s.tradeDate == today and s.status == EntityStatus.ACTIVE
        )

    def is_running(self, session_id: int) -> bool:
        t = self._tasks.get(session_id)
        return t is not None and not t.done()

    def start(self, session_id: int) -> None:
        if self.is_running(session_id):
            return
        self._tasks[session_id] = asyncio.create_task(self._run(session_id), name=f"session-loop-{session_id}")
        logger.info(f"session loop started: session={session_id}")

    def stop(self, session_id: int) -> None:
        t = self._tasks.pop(session_id, None)
        if t and not t.done():
            t.cancel()
            logger.info(f"session loop stopped: session={session_id}")
        self._snapshots.pop(session_id, None)
        self._keys.pop(session_id, None)
        self._close_subscribers(session_id)

    def sync(self, s: TradingSession) -> None:
        """Start the loop if this session should run one, stop it if not. Call after the row is committed."""
        if self.eligible(s):
            self.start(s.id)
        else:
            self.stop(s.id)

    async def resume_today(self) -> int:
        """Startup: restart the loop of every ACTIVE session dated today."""
        today = datetime.now(UTC).astimezone(_IST).date().isoformat()
        async with self._factory() as db:
            rows = (await db.execute(
                select(TradingSession.id)
                .where(TradingSession.status == EntityStatus.ACTIVE)
                .where(TradingSession.sessionStatus == "ACTIVE")
                .where(TradingSession.sessionType.in_(("MANUAL", "SEMI_AUTO", "FULL_AUTO")))
                .where(TradingSession.tradeDate == today)
            )).scalars().all()
        for sid in rows:
            self.start(sid)
        return len(rows)

    async def stop_all(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._snapshots.clear()
        for sid in list(self._subs):
            self._close_subscribers(sid)

    # ───────────────────────── read ─────────────────────────
    def snapshot(self, session_id: int) -> SessionLoopResponse | None:
        """Latest tick result with the clock-dependent fields refreshed (the offer keeps counting down
        between ticks)."""
        snap = self._snapshots.get(session_id)
        if snap is None:
            return None
        now = datetime.now(UTC)
        picks = []
        for pick in snap.picks:
            if pick.pickState == "OFFERED":
                left = (pick.expiresAt - now).total_seconds()
                pick = pick.model_copy(update={
                    "secondsLeft": round(max(0.0, left), 2),
                    "pickState": "OFFERED" if left > 0 else "EXPIRED",
                })
            picks.append(pick)
        return snap.model_copy(update={"serverTime": now, "picks": picks})

    # ───────────────────────── push (SSE) ─────────────────────────
    def subscribe(self, session_id: int) -> asyncio.Queue:
        """A queue of loop updates for one SSE client. Items: SessionLoopResponse, or None = loop has ended."""
        q: asyncio.Queue = asyncio.Queue(maxsize=16)
        self._subs.setdefault(session_id, set()).add(q)
        return q

    def unsubscribe(self, session_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(session_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(session_id, None)

    @staticmethod
    def _put(q: asyncio.Queue, item: SessionLoopResponse | None) -> None:
        if q.full():  # a slow client only ever needs the newest state
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(item)

    def _close_subscribers(self, session_id: int) -> None:
        for q in list(self._subs.get(session_id, ())):
            self._put(q, None)

    @staticmethod
    def _change_key(snap: SessionLoopResponse) -> str:
        """Everything a client can see EXCEPT the clocks (it counts down from expiresAt itself)."""
        d = snap.model_dump(mode="json", exclude={"serverTime"})
        for p in d.get("picks", []):
            p.pop("secondsLeft", None)
        return json.dumps(d, sort_keys=True, default=str)

    def _publish(self, session_id: int, snap: SessionLoopResponse) -> None:
        """Push to SSE clients only when something they can see changed."""
        key = self._change_key(snap)
        if self._keys.get(session_id) == key:
            return
        self._keys[session_id] = key
        fresh = self.snapshot(session_id)
        for q in list(self._subs.get(session_id, ())):
            self._put(q, fresh)

    # ───────────────────────── the loop ─────────────────────────
    async def _run(self, session_id: int) -> None:
        try:
            while True:
                delay = self._tick_seconds
                try:
                    async with self._factory() as db:
                        snap = await self.service.tick(db, session_id)
                        await db.commit()
                    self._snapshots[session_id] = snap
                    self._publish(session_id, snap)
                    if snap.state in STOP_STATES:
                        return
                except NotFoundException:
                    self._snapshots.pop(session_id, None)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001 -- the loop must survive a bad tick
                    logger.error(f"session loop tick failed: session={session_id} {type(e).__name__}: {e}")
                    delay = ERROR_BACKOFF_SECONDS
                await asyncio.sleep(delay)
        finally:
            if self._tasks.get(session_id) is asyncio.current_task():
                self._tasks.pop(session_id, None)
                self._close_subscribers(session_id)


session_loop_runner = SessionLoopRunner()
