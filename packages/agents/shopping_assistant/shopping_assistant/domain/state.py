"""Shopping agent graph state (domain-owned; no FastAPI imports)."""

from __future__ import annotations

from typing import Any, TypedDict


class ShoppingGraphState(TypedDict, total=False):
    """State carried through the shopping LangGraph workflow."""

    shopping_request_id: str
    user_message: str
    assistant_message: str
    mode: str
    preferences: dict[str, Any]
    search_plan: dict[str, Any]
    products: list[dict[str, Any]]
    # Pipeline handoff (serialized products; avoids underscore keys dropped by LangGraph)
    shopping_catalog: list[dict[str, Any]]
    shopping_candidates: list[dict[str, Any]]
    shopping_ranked: list[dict[str, Any]]
    shopping_relaxed: bool
    shopping_retrieval_notes: list[str]
