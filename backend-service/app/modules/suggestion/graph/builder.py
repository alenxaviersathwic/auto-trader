from langgraph.graph import END, START, StateGraph

from app.modules.suggestion.graph import nodes
from app.modules.suggestion.graph.state import SuggestionState, UnderlyingState


def build_underlying_graph():
    """Per-underlying branch: gather -> build menu -> (reuse | AI select) -> validate."""
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


def build_suggestion_graph():
    """One suggestion run: load research -> parallel per-underlying branches -> pick -> save -> track."""
    g = StateGraph(SuggestionState)
    g.add_node("load_research", nodes.load_research)
    g.add_node("analyze_underlying", nodes.analyze_underlying)
    g.add_node("pick_top", nodes.pick_top)
    g.add_node("save_picks", nodes.save_picks)
    g.add_node("track_outcomes", nodes.track_outcomes)
    g.add_edge(START, "load_research")
    g.add_conditional_edges("load_research", nodes.route_after_research, ["analyze_underlying", END])
    g.add_edge("analyze_underlying", "pick_top")
    g.add_edge("pick_top", "save_picks")
    g.add_edge("save_picks", "track_outcomes")
    g.add_edge("track_outcomes", END)
    return g.compile()


underlying_graph = build_underlying_graph()
suggestion_graph = build_suggestion_graph()
