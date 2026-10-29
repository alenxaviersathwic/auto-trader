from langgraph.graph import END, START, StateGraph

from app.modules.suggestion.graph import nodes
from app.modules.suggestion.graph.state import UnderlyingState


def build_underlying_graph():
    """One iteration of one card: gather -> build menu -> (reuse | AI select) -> validate."""
    g = StateGraph(UnderlyingState)
    g.add_node("gather", nodes.gather)
    g.add_node("make_menu", nodes.make_menu)
    g.add_node("ai_select", nodes.ai_select)
    g.add_node("validate", nodes.validate)
    g.add_edge(START, "gather")
    g.add_conditional_edges("gather", lambda s: "end" if s.get("error") else "make_menu",
                            {"end": END, "make_menu": "make_menu"})
    g.add_conditional_edges("make_menu", nodes.route_after_menu,
                            {"end": END, "validate": "validate", "ai_select": "ai_select"})
    g.add_edge("ai_select", "validate")
    g.add_edge("validate", END)
    return g.compile()


underlying_graph = build_underlying_graph()
