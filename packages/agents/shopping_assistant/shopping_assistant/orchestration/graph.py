"""Shopping LangGraph: guard → load → extract → retrieve → rank → plan → respond."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from shopping_assistant.domain.state import ShoppingGraphState
from shopping_assistant.orchestration.nodes import (
    node_build_search_plan,
    node_extract_preferences,
    node_generate_response,
    node_guard_input,
    node_load_catalog,
    node_rank_candidates,
    node_retrieve_candidates,
    route_after_guard,
    route_after_load,
)

_COMPILED_GRAPH: Any | None = None


def build_shopping_graph() -> Any:
    """Compile the product-aware pipeline (deterministic + optional LLM reply)."""
    graph = StateGraph(ShoppingGraphState)

    graph.add_node("guard_input", node_guard_input)
    graph.add_node("load_catalog", node_load_catalog)
    graph.add_node("extract_preferences", node_extract_preferences)
    graph.add_node("retrieve_candidates", node_retrieve_candidates)
    graph.add_node("rank_candidates", node_rank_candidates)
    graph.add_node("build_search_plan", node_build_search_plan)
    graph.add_node("generate_response", node_generate_response)

    graph.add_edge(START, "guard_input")
    graph.add_conditional_edges(
        "guard_input",
        route_after_guard,
        {
            "load_catalog": "load_catalog",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "load_catalog",
        route_after_load,
        {
            "extract_preferences": "extract_preferences",
            END: END,
        },
    )
    graph.add_edge("extract_preferences", "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "rank_candidates")
    graph.add_edge("rank_candidates", "build_search_plan")
    graph.add_edge("build_search_plan", "generate_response")
    graph.add_edge("generate_response", END)
    return graph.compile()


def get_shopping_graph() -> Any:
    """Lazy singleton compiled graph (process-local)."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_shopping_graph()
    return _COMPILED_GRAPH


def run_shopping_turn(user_message: str) -> ShoppingGraphState:
    """Run one graph invocation (sync; call from a thread in async routes if needed)."""
    graph = get_shopping_graph()
    result: ShoppingGraphState = graph.invoke({"user_message": user_message})
    return result
