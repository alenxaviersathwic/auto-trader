import asyncio
from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import async_session_factory
from app.core.exception.app_exceptions import BusinessException, NotFoundException
from app.core.logging.logger import logger
from app.modules.master.entity.master_message_entity import MasterMessage
from app.modules.master.entity.master_run_entity import MasterRun
from app.modules.master.graph.builder import MasterWorkflowRunner
from app.modules.master.graph.nodes.master_nodes import MasterNodes
from app.modules.master.graph.state import MasterState
from app.modules.master.llm.fake_llm import FakeLlmClient
from app.modules.master.llm.llm_client import LlmClient
from app.modules.master.llm.ollama_client import OllamaClient
from app.modules.master.mcp.server_registry import ServerRegistry
from app.modules.master.repository.conversation_repository import ConversationRepository
from app.modules.master.repository.master_config_repository import MasterConfigRepository
from app.modules.master.repository.message_repository import MessageFilter, MessageRepository
from app.modules.master.repository.preference_repository import PreferenceRepository
from app.modules.master.repository.proposal_repository import ProposalRepository
from app.modules.master.repository.run_repository import RunRepository
from app.modules.master.repository.tool_call_repository import ToolCallRepository
from app.modules.master.repository.tool_server_repository import ToolServerRepository
from app.modules.master.service.redaction_service import RedactionService, SECRET_NOTICE
from app.modules.master.service.tool_gateway import ToolGateway

# In-memory SSE pub/sub queues per run
_EVENT_QUEUES: Dict[int, List[asyncio.Queue]] = {}


class RunService:
    """
    Manages execution runs for master chat messages, LangGraph execution, and SSE event streaming.
    """

    def __init__(
        self,
        run_repo: Optional[RunRepository] = None,
        message_repo: Optional[MessageRepository] = None,
        conv_repo: Optional[ConversationRepository] = None,
        config_repo: Optional[MasterConfigRepository] = None,
        llm_client: Optional[LlmClient] = None,
    ):
        self.run_repo = run_repo or RunRepository()
        self.message_repo = message_repo or MessageRepository()
        self.conv_repo = conv_repo or ConversationRepository()
        self.config_repo = config_repo or MasterConfigRepository()
        self.llm = llm_client or OllamaClient()

        # Gateway & Nodes
        self.tool_call_repo = ToolCallRepository()
        self.tool_server_repo = ToolServerRepository()
        self.gateway = ToolGateway(
            config_repo=self.config_repo,
            tool_server_repo=self.tool_server_repo,
            tool_call_repo=self.tool_call_repo,
        )
        self.proposal_repo = ProposalRepository()
        self.preference_repo = PreferenceRepository()
        self.server_registry = ServerRegistry(self.tool_server_repo)

        self.nodes = MasterNodes(
            llm_client=self.llm,
            tool_gateway=self.gateway,
            proposal_repo=self.proposal_repo,
            preference_repo=self.preference_repo,
            config_repo=self.config_repo,
        )
        self.workflow_runner = MasterWorkflowRunner(self.nodes)

    def set_llm(self, llm: LlmClient) -> None:
        self.llm = llm
        self.nodes.llm = llm

    async def get_run(self, session: AsyncSession, run_id: int) -> MasterRun:
        run = await self.run_repo.get_by_id(session, run_id)
        if not run:
            raise NotFoundException(message=f"Run #{run_id} not found")
        return run

    async def cancel_run(self, session: AsyncSession, run_id: int) -> MasterRun:
        run = await self.get_run(session, run_id)
        if run.state in ["COMPLETED", "FAILED", "CANCELLED"]:
            return run
        run.state = "CANCELLED"
        run.finishedAt = datetime.now(timezone.utc)
        saved = await self.run_repo.save(session, run)
        await self._publish_event(run_id, {"event": "run.failed", "error": "Run was cancelled by user"})
        return saved

    async def send_user_message(
        self,
        session: AsyncSession,
        conversation_id: int,
        content: str,
        choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Receives user prompt, redacts secrets, records message, creates run, and spawns graph execution.
        Returns {messageId, runId}.
        """
        # Ensure MCP server registry defaults are loaded
        await self.server_registry.ensure_defaults(session)

        # 1. Redaction of secrets in incoming text
        redacted_content, was_redacted = RedactionService.redact_text(content)
        if was_redacted:
            redacted_content += SECRET_NOTICE

        # Append choice if present
        if choice:
            redacted_content = f"{redacted_content}\n[Selected Option: {choice}]"

        # 2. Get sequence number and save user message
        seq = await self.message_repo.get_next_seq(session, conversation_id)
        user_msg = MasterMessage(
            conversationId=conversation_id,
            seq=seq,
            role="USER",
            content=redacted_content,
            redacted=was_redacted,
        )
        user_msg = await self.message_repo.save(session, user_msg)

        # 3. Create run
        thread_id = f"conv-{conversation_id}"
        run = MasterRun(
            conversationId=conversation_id,
            userMessageId=user_msg.id,
            state="RUNNING",
            threadId=thread_id,
            startedAt=datetime.now(timezone.utc),
        )
        run = await self.run_repo.save(session, run)

        user_msg.runId = run.id
        await self.message_repo.save(session, user_msg)

        # Update conversation timestamp & count
        conv = await self.conv_repo.get_by_id(session, conversation_id)
        if conv:
            conv.lastMessageAt = datetime.now(timezone.utc)
            conv.messageCount += 1
            if conv.title == "New Conversation" and len(content) > 3:
                conv.title = content[:80].strip()
            await self.conv_repo.save(session, conv)

        # 4. Spawn background task to run LangGraph
        asyncio.create_task(self._execute_run_in_background(run.id, conversation_id, user_msg.id, redacted_content))

        return {
            "messageId": user_msg.id,
            "runId": run.id,
        }

    async def _execute_run_in_background(
        self,
        run_id: int,
        conversation_id: int,
        user_message_id: int,
        user_content: str,
    ) -> None:
        """Executes LangGraph workflow in detached async context with fresh DB session."""
        async with async_session_factory() as session:
            try:
                run = await self.run_repo.get_by_id(session, run_id)
                if not run:
                    return

                # Load conversation history
                history_msgs = await self.message_repo.get_recent_history(session, conversation_id, limit=10)
                formatted_history = [
                    {"role": m.role.lower(), "content": m.content}
                    for m in history_msgs
                    if m.id != user_message_id
                ]

                # Initial state
                state = MasterState(
                    conversationId=conversation_id,
                    runId=run_id,
                    userText=user_content,
                    history=formatted_history,
                )

                await self._publish_event(run_id, {"event": "run.started", "runId": run_id})

                # Run workflow
                state = await self.workflow_runner.run(state, session)

                # Forward all state events to pub/sub queues
                for ev in state.events:
                    await self._publish_event(run_id, ev)

                # Create assistant message in conversation
                if state.answerDraft:
                    seq = await self.message_repo.get_next_seq(session, conversation_id)
                    blocks = []
                    if state.proposalId:
                        blocks.append({"type": "PROPOSAL_REF", "proposalId": state.proposalId})
                    if state.questions:
                        blocks.append({"type": "QUESTION", "questions": state.questions})

                    asst_msg = MasterMessage(
                        conversationId=conversation_id,
                        seq=seq,
                        role="ASSISTANT",
                        content=state.answerDraft,
                        blocks=blocks if blocks else None,
                        runId=run_id,
                    )
                    await self.message_repo.save(session, asst_msg)

                # Finalize run
                run.state = "WAITING_USER" if state.interruptWaiting else "COMPLETED"
                run.intent = state.intent
                run.clarificationRound = state.clarificationRound
                run.finishedAt = datetime.now(timezone.utc)
                await self.run_repo.save(session, run)

                if state.interruptWaiting:
                    await self._publish_event(run_id, {"event": "run.waiting"})
                else:
                    await self._publish_event(run_id, {"event": "run.completed", "proposalId": state.proposalId})

                await session.commit()

            except Exception as e:
                logger.error(f"Error in background run execution #{run_id}: {e}", exc_info=True)
                await self._publish_event(run_id, {"event": "run.failed", "error": str(e)})
                try:
                    # Create assistant recovery message so the user is never left without a response
                    recovery_text = "I encountered an issue processing that request. Please try asking again or describe your strategy/rule in detail."
                    try:
                        reply = await self.llm.generate(
                            [{"role": "user", "content": user_content}],
                            system_prompt="You are AI Master for Auto-Trader. The user sent a request. Answer conversationally and helpfully.",
                            temperature=0.3,
                        )
                        if reply and reply.strip():
                            recovery_text = reply.strip()
                    except Exception:
                        pass

                    seq = await self.message_repo.get_next_seq(session, conversation_id)
                    asst_msg = MasterMessage(
                        conversationId=conversation_id,
                        seq=seq,
                        role="ASSISTANT",
                        content=recovery_text,
                        runId=run_id,
                    )
                    await self.message_repo.save(session, asst_msg)

                    run = await self.run_repo.get_by_id(session, run_id)
                    if run:
                        run.state = "COMPLETED"
                        run.error = None
                        run.finishedAt = datetime.now(timezone.utc)
                        await self.run_repo.save(session, run)
                    await session.commit()
                except Exception as save_err:
                    logger.error(f"Failed to record recovery message for run #{run_id}: {save_err}")
                    pass

    async def _publish_event(self, run_id: int, event_data: Dict[str, Any]) -> None:
        queues = _EVENT_QUEUES.get(run_id, [])
        for q in queues:
            await q.put(event_data)

    async def stream_events(self, run_id: int) -> AsyncGenerator[str, None]:
        """SSE generator emitting real-time events for a run."""
        q = asyncio.Queue()
        _EVENT_QUEUES.setdefault(run_id, []).append(q)

        try:
            while True:
                try:
                    # Timeout after 15s to emit heartbeat
                    event_data = await asyncio.wait_for(q.get(), timeout=15.0)
                    ev_name = event_data.get("event", "message")
                    yield f"event: {ev_name}\ndata: {json.dumps(event_data)}\n\n"

                    if ev_name in ["run.completed", "run.failed", "run.waiting"]:
                        break

                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'time': datetime.now(timezone.utc).isoformat()})}\n\n"

        finally:
            if run_id in _EVENT_QUEUES and q in _EVENT_QUEUES[run_id]:
                _EVENT_QUEUES[run_id].remove(q)
                if not _EVENT_QUEUES[run_id]:
                    _EVENT_QUEUES.pop(run_id, None)
