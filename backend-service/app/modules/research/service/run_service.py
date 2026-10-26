import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import AppException
from app.core.logging.logger import logger
from app.modules.research.entity.research_entity import ResearchCandidate, ResearchRun
from app.modules.research.graph.builder import ResearchWorkflowRunner
from app.modules.research.graph.state import ResearchState


class RunService:
    """
    Manages execution lifecycle, concurrency locking, and event broadcasting for research runs.
    """

    def __init__(self):
        self._active_run_id: Optional[int] = None
        self._active_task: Optional[asyncio.Task] = None
        self._active_state: Optional[ResearchState] = None
        self._event_queues: Dict[int, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def get_active_run_id(self, session: AsyncSession) -> Optional[int]:
        """Checks DB for any run in QUEUED or RUNNING state."""
        res = await session.execute(
            select(ResearchRun.id)
            .where(ResearchRun.status == 1)
            .where(ResearchRun.state.in_(["QUEUED", "RUNNING"]))
            .order_by(ResearchRun.id.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def start_run(
        self,
        scope: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        trigger_source: str = "UI",
        triggered_by: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        Starts a background research run. Rejects if a run is already active (409 Conflict).
        """
        async with self._lock:
            # 1. Enforce single run concurrency lock
            active_id = await self.get_active_run_id(session) if session else self._active_run_id
            if active_id is not None:
                raise AppException(
                    status_code=409,
                    message="A research run is already in progress. Please wait for it to complete or cancel it.",
                )

            scope_list = scope or ["INDEX", "COMMODITY"]
            run_params = params or {}
            window_hours = run_params.get("windowHours", 24)
            if window_hours > 48 or window_hours < 6:
                raise AppException(
                    status_code=422,
                    message="Freshness windowHours must be between 6 and 48 hours.",
                )

            # 2. Persist new run
            run_row = ResearchRun(
                scope=scope_list,
                triggerSource=trigger_source,
                triggeredBy=triggered_by,
                state="QUEUED",
                params=run_params,
                configVersion=1,
                threadId=f"thread-research-{int(datetime.now().timestamp())}",
            )
            session.add(run_row)
            await session.commit()
            run_id = run_row.id

            self._active_run_id = run_id
            self._event_queues[run_id] = []

            # 3. Spawn background execution task
            task = asyncio.create_task(self._execute_run_background(run_id, scope_list, run_params))
            self._active_task = task
            return run_id

    async def _execute_run_background(
        self, run_id: int, scope: List[str], params: Dict[str, Any]
    ) -> None:
        """Internal background task handler running the LangGraph workflow."""
        runner = ResearchWorkflowRunner()
        state = ResearchState(runId=run_id, scope=scope, params=params)
        self._active_state = state

        await self._broadcast_event(run_id, "run.started", {"runId": run_id, "scope": scope})

        async def on_progress(updated_state: ResearchState):
            await self._broadcast_event(
                run_id,
                "node.progress",
                {
                    "runId": run_id,
                    "node": updated_state.currentNode,
                    "progressPct": updated_state.progressPct,
                    "stats": updated_state.stats,
                },
            )
            try:
                async with async_session_factory() as s:
                    await s.execute(
                        update(ResearchRun)
                        .where(ResearchRun.id == run_id)
                        .values(
                            currentNode=updated_state.currentNode,
                            progressPct=updated_state.progressPct,
                        )
                    )
                    await s.commit()
            except Exception:
                pass

        try:
            async with async_session_factory() as session:
                # Mark as RUNNING
                await session.execute(
                    update(ResearchRun)
                    .where(ResearchRun.id == run_id)
                    .values(state="RUNNING", startedAt=datetime.now(timezone.utc))
                )
                await session.commit()

                await runner.run(state, session, progress_callback=on_progress)

            await self._broadcast_event(
                run_id,
                "run.completed",
                {"runId": run_id, "stats": state.stats, "state": state.state},
            )

        except asyncio.CancelledError:
            logger.info(f"Research run {run_id} cancelled.")
            await self._broadcast_event(run_id, "run.cancelled", {"runId": run_id})
        except Exception as e:
            logger.error(f"Research run {run_id} failed: {e}")
            await self._broadcast_event(run_id, "run.failed", {"runId": run_id, "error": str(e)})
        finally:
            self._active_run_id = None
            self._active_task = None
            self._active_state = None

    async def cancel_run(self, run_id: int, session: AsyncSession) -> None:
        """Cancels an in-progress run."""
        async with self._lock:
            if self._active_run_id == run_id and self._active_state:
                self._active_state.isCancelled = True
            if self._active_task and not self._active_task.done():
                self._active_task.cancel()

            await session.execute(
                update(ResearchRun)
                .where(ResearchRun.id == run_id)
                .values(state="CANCELLED", finishedAt=datetime.now(timezone.utc))
            )
            await session.commit()
            self._active_run_id = None
            self._active_task = None
            self._active_state = None

    async def resume_run(self, run_id: int, session: AsyncSession) -> int:
        """Resumes a failed, resumable run."""
        run_res = await session.execute(select(ResearchRun).where(ResearchRun.id == run_id))
        run = run_res.scalar_one_or_none()
        if not run:
            raise AppException(status_code=404, message="Run not found")
        if run.state != "FAILED" or not run.resumable:
            raise AppException(status_code=400, message="Only failed, resumable runs can be resumed")

        # Resume as a new run with previous parameters
        return await self.start_run(
            scope=run.scope,
            params=run.params,
            trigger_source="API",
            triggered_by="resume",
            session=session,
        )

    async def register_listener(self, run_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._event_queues.setdefault(run_id, []).append(q)
        return q

    def unregister_listener(self, run_id: int, q: asyncio.Queue) -> None:
        if run_id in self._event_queues:
            if q in self._event_queues[run_id]:
                self._event_queues[run_id].remove(q)

    async def _broadcast_event(self, run_id: int, event_name: str, data: Dict[str, Any]) -> None:
        payload = {"event": event_name, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}
        for q in self._event_queues.get(run_id, []):
            await q.put(payload)

    async def event_generator(self, run_id: int) -> AsyncGenerator[str, None]:
        """SSE event generator with 15-second heartbeat."""
        q = await self.register_listener(run_id)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                    import json
                    yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
                    if item["event"] in ["run.completed", "run.failed", "run.cancelled"]:
                        break
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
        finally:
            self.unregister_listener(run_id, q)

    @staticmethod
    def _candidate_to_dict(c: ResearchCandidate) -> Dict[str, Any]:
        return {
            "id": c.id,
            "runId": c.runId,
            "scope": c.underlyingType,
            "item": c.underlyingCode,
            "underlyingType": c.underlyingType,
            "underlyingCode": c.underlyingCode,
            "status": c.newsStatus,
            "newsStatus": c.newsStatus,
            "suggested": c.suggested,
            "rank": c.rank,
            "direction": c.direction,
            "bearishWatch": c.bearishWatch,
            "score": float(c.score) if c.score is not None else None,
            "latestScore": float(c.score) if c.score is not None else None,
            "scoreLabel": c.scoreLabel,
            "positiveWeight": float(c.positiveWeight) if c.positiveWeight is not None else 0.0,
            "negativeWeight": float(c.negativeWeight) if c.negativeWeight is not None else 0.0,
            "negativeShare": float(c.negativeShare) if c.negativeShare is not None else 0.0,
            "positiveClaims": c.positiveClaims or 0,
            "negativeClaims": c.negativeClaims or 0,
            "independentSources": c.independentSources or 0,
            "freshArticleCount": c.freshArticleCount or 0,
            "flags": c.flags or [],
            "reasons": c.reasons or [],
            "thesis": c.thesis,
            "supportingPoints": c.supportingPoints or [],
            "watchItems": c.watchItems or [],
            "latestNews": c.latestNews or [],
            "affectNews": c.affectNews or [],
            "neutralNews": c.neutralNews or [],
            "blogSummary": c.blogSummary,
            "hasVectorEmbedding": c.briefEmbedding is not None,
            "createdAt": c.createdAt.isoformat() if c.createdAt else None,
        }

    async def get_latest_results(
        self, underlying_type: str, session: AsyncSession
    ) -> Dict[str, Any]:
        """Returns the latest completed research candidates grouped by status."""
        run_res = await session.execute(
            select(ResearchRun)
            .where(ResearchRun.status == 1)
            .where(ResearchRun.state.in_(["COMPLETED", "PARTIAL"]))
            .order_by(ResearchRun.finishedAt.desc().nulls_last(), ResearchRun.id.desc())
            .limit(1)
        )
        last_run = run_res.scalar_one_or_none()
        if not last_run:
            return {
                "run": None,
                "suggested": [],
                "bearishWatch": [],
                "hasNegative": [],
                "mixed": [],
                "clearNeutral": [],
                "noCoverage": [],
            }

        cand_res = await session.execute(
            select(ResearchCandidate)
            .where(ResearchCandidate.status == 1)
            .where(ResearchCandidate.runId == last_run.id)
            .where(ResearchCandidate.underlyingType == underlying_type.upper())
            .order_by(ResearchCandidate.rank.asc().nulls_last())
        )
        candidates = cand_res.scalars().all()

        suggested = [self._candidate_to_dict(c) for c in candidates if c.suggested]
        bearish_watch = [self._candidate_to_dict(c) for c in candidates if c.bearishWatch]
        has_negative = [
            self._candidate_to_dict(c)
            for c in candidates
            if c.newsStatus == "HAS_NEGATIVE" and not c.bearishWatch
        ]
        mixed = [self._candidate_to_dict(c) for c in candidates if c.newsStatus == "MIXED"]
        clear_neutral = [
            self._candidate_to_dict(c) for c in candidates if c.newsStatus == "CLEAR_NEUTRAL"
        ]
        no_coverage = [
            self._candidate_to_dict(c) for c in candidates if c.newsStatus == "NO_COVERAGE"
        ]

        now = datetime.now(timezone.utc)
        age_hours = 0.0
        if last_run.finishedAt:
            age_hours = round((now - last_run.finishedAt).total_seconds() / 3600.0, 1)

        return {
            "run": {
                "id": last_run.id,
                "state": last_run.state,
                "finishedAt": last_run.finishedAt.isoformat() if last_run.finishedAt else None,
                "ageHours": age_hours,
                "windowHours": last_run.params.get("windowHours", 24),
                "scope": last_run.scope,
            },
            "suggested": suggested,
            "bearishWatch": bearish_watch,
            "hasNegative": has_negative,
            "mixed": mixed,
            "clearNeutral": clear_neutral,
            "noCoverage": no_coverage,
        }

    async def trigger_or_get_active_run(
        self,
        scope: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Triggers a research run if idle, or returns the currently active run."""
        active_id = await self.get_active_run_id(session) if session else self._active_run_id
        if active_id is not None:
            active_info = await self.get_current_status(session) if session else None
            return active_info or {"runId": active_id, "state": "RUNNING"}

        run_id = await self.start_run(
            scope=scope or ["INDEX", "COMMODITY"],
            params=params or {"windowHours": 24, "topN": 5},
            trigger_source="API",
            session=session,
        )
        return {"runId": run_id, "state": "QUEUED", "progressPct": 0}

    async def get_current_status(self, session: AsyncSession) -> Dict[str, Any]:
        """Returns whether the research engine is running and its progress percentage."""
        active_id = await self.get_active_run_id(session)
        target_id = active_id
        if not target_id:
            latest_res = await session.execute(
                select(ResearchRun.id).order_by(ResearchRun.id.desc()).limit(1)
            )
            target_id = latest_res.scalar_one_or_none()

        if not target_id:
            return {
                "isRunning": False,
                "state": "IDLE",
                "progressPct": 0,
                "currentNode": None,
                "startedAt": None,
                "finishedAt": None,
            }

        run_res = await session.execute(select(ResearchRun).where(ResearchRun.id == target_id))
        r = run_res.scalar_one_or_none()
        if not r:
            return {
                "isRunning": False,
                "state": "IDLE",
                "progressPct": 0,
                "currentNode": None,
                "startedAt": None,
                "finishedAt": None,
            }

        cur_node = r.currentNode
        prog_pct = r.progressPct
        if self._active_state and self._active_state.runId == r.id:
            cur_node = self._active_state.currentNode or cur_node
            prog_pct = self._active_state.progressPct or prog_pct

        is_running = r.state in ["RUNNING", "QUEUED"]
        return {
            "isRunning": is_running,
            "state": r.state,
            "progressPct": prog_pct if is_running else (100 if r.state == "COMPLETED" else 0),
            "currentNode": cur_node if is_running else None,
            "startedAt": r.startedAt.isoformat() if r.startedAt else None,
            "finishedAt": r.finishedAt.isoformat() if r.finishedAt else None,
        }

    async def cancel_active_run(self, session: AsyncSession) -> Dict[str, Any]:
        """Cancels the current running pipeline without needing to pass an ID."""
        active_id = await self.get_active_run_id(session)
        if active_id:
            await self.cancel_run(active_id, session)
            return {"cancelled": True, "runId": active_id}
        return {"cancelled": False, "message": "No active run to cancel"}


run_service = RunService()
