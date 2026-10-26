from typing import Any, Callable, Optional
from langgraph.graph import StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.research.graph.nodes.research_nodes import ResearchNodes
from app.modules.research.graph.state import ResearchState


class ResearchWorkflowRunner:
    """
    Executes the Research Engine pipeline step-by-step with state persistence,
    cancellation points, and progress tracking.
    """

    def __init__(self, nodes: Optional[ResearchNodes] = None):
        self.nodes = nodes or ResearchNodes()

    async def run(
        self,
        state: ResearchState,
        session: AsyncSession,
        progress_callback: Optional[Callable[[ResearchState], Any]] = None,
    ) -> ResearchState:
        """Executes full research run lifecycle."""
        pipeline_steps = [
            ("load_context", self.nodes.load_context),
            ("plan_queries", self.nodes.plan_queries),
            ("discover_stocks", self.nodes.discover_stocks),
            ("search_and_fetch", self.nodes.search_and_fetch),
            ("clean_filter_dedupe", self.nodes.clean_filter_dedupe),
            ("embed_chunks", self.nodes.embed_chunks),
            ("extract_claims", self.nodes.extract_claims),
            ("verify_claims", self.nodes.verify_claims),
            ("negative_sweep", self.nodes.negative_sweep),
            ("classify_status", self.nodes.classify_status),
            ("score_rank", self.nodes.score_rank),
            ("write_briefs", self.nodes.write_briefs),
            ("persist", self.nodes.persist),
            ("finalize", self.nodes.finalize),
        ]

        try:
            for step_name, step_fn in pipeline_steps:
                if state.isCancelled:
                    state.state = "CANCELLED"
                    break

                state = await step_fn(state, session)
                if progress_callback:
                    await progress_callback(state)

        except Exception as e:
            state.state = "FAILED"
            state.error = str(e)
            state = await self.nodes.finalize(state, session)
            raise

        return state
