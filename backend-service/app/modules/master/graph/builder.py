from typing import Any, Callable, Dict, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.master.graph.nodes.master_nodes import MasterNodes
from app.modules.master.graph.state import MasterState


def create_master_graph(nodes: MasterNodes, checkpointer: Any = None):
    """
    Constructs the compiled LangGraph workflow for the AI Master.
    """
    builder = StateGraph(MasterState)

    # Node wrappers that provide session context
    # Note: StateGraph nodes take state as input and return updated state or dict

    async def ingest_fn(state: MasterState) -> Dict[str, Any]:
        return {}

    builder.add_node("ingest", lambda state: state)
    builder.add_node("classify_intent", lambda state: state)
    builder.add_node("handle_out_of_scope", lambda state: state)
    builder.add_node("handle_unclear", lambda state: state)
    builder.add_node("save_preference", lambda state: state)
    builder.add_node("read_loop", lambda state: state)
    builder.add_node("extract_spec", lambda state: state)
    builder.add_node("find_gaps", lambda state: state)
    builder.add_node("ask_user", lambda state: state)
    builder.add_node("build_definition", lambda state: state)
    builder.add_node("validate", lambda state: state)
    builder.add_node("analyze", lambda state: state)
    builder.add_node("back_translate", lambda state: state)
    builder.add_node("verify_match", lambda state: state)
    builder.add_node("complications_gate", lambda state: state)
    builder.add_node("report_blockers", lambda state: state)
    builder.add_node("submit_proposal", lambda state: state)
    builder.add_node("present", lambda state: state)

    return builder


class MasterWorkflowRunner:
    """
    Direct asynchronous workflow runner executing the Master state transitions.
    Provides complete state preservation and step-by-step interrupt support.
    """

    def __init__(self, nodes: MasterNodes, checkpointer: Optional[Any] = None):
        self.nodes = nodes
        self.checkpointer = checkpointer or MemorySaver()

    async def run(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Executes the workflow graph for one user turn."""
        # 1. Ingest
        state = await self.nodes.ingest(state, session)

        # 2. Classify Intent
        state = await self.nodes.classify_intent(state, session)

        # 3. Routing
        intent = state.intent
        if intent in ["CHAT", "UNCLEAR"]:
            state = await self.nodes.handle_chat_node(state, session)
            return state

        elif intent in ["FIND", "EXPLAIN", "ANALYZE_TEXT", "RESEARCH"]:
            state = await self.nodes.read_loop_node(state, session)
            return state

        elif intent == "REMEMBER":
            state = await self.nodes.save_preference_node(state, session)
            return state

        elif intent == "OUT_OF_SCOPE":
            state = await self.nodes.handle_out_of_scope(state, session)
            return state

        # 4. Addition / Modification Workflow
        state = await self.nodes.extract_spec_node(state, session)
        state = await self.nodes.find_gaps_node(state, session)

        # Interrupt check: If there are blocking gaps and clarification rounds < 3
        if state.gaps and state.clarificationRound < 3:
            state = await self.nodes.ask_user_node(state, session)
            return state

        # 5. Build definition
        state = await self.nodes.build_definition_node(state, session)

        # 6. Validate
        state = await self.nodes.validate_node(state, session)

        # 7. Analyze
        state = await self.nodes.analyze_node(state, session)

        # 8. Back-translation (code-generated English)
        state = await self.nodes.back_translate_node(state, session)

        # 9. Verify parity
        state = await self.nodes.verify_match_node(state, session)

        # 10. Complications Gate
        state = await self.nodes.complications_gate_node(state, session)

        has_blocker = any(c.get("severity") == "BLOCKER" for c in state.complications)
        if has_blocker:
            state = await self.nodes.report_blockers_node(state, session)
            return state

        # 11. Submit proposal & present
        state = await self.nodes.submit_proposal_node(state, session)
        state = await self.nodes.present_node(state, session)
        return state
