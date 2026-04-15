"""LangGraph node functions for the shopping pipeline (all logic in this package)."""

from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END

from shopping_assistant.domain.models import (
    Product,
    SearchPlan,
    preferences_from_public,
)
from shopping_assistant.domain.state import ShoppingGraphState
from shopping_assistant.orchestration.response_llm import try_generate_llm_reply
from shopping_assistant.service.deterministic import (
    _format_reply,
    _product_to_card,
    assess_match_quality,
    build_search_plan,
    catalog_category_slugs,
    extract_preferences,
    load_product_catalog,
    rank_products,
    retrieve_candidates_with_relaxation,
)

logger = logging.getLogger(__name__)

_FALLBACK_PLAN: dict[str, Any] = {
    "intent": "none",
    "filters_applied": [],
    "sort": "n/a",
    "relaxed": False,
}


def _error_plan(intent: str) -> dict[str, Any]:
    return {
        "intent": intent,
        "filters_applied": [],
        "sort": "n/a",
        "relaxed": False,
    }


def node_guard_input(state: ShoppingGraphState) -> dict[str, Any]:
    """Reject empty user input."""
    msg = (state.get("user_message") or "").strip()
    if not msg:
        return {
            "assistant_message": (
                "Please send a non-empty message so I can search the catalog."
            ),
            "mode": "fallback",
            "preferences": {},
            "search_plan": {**_FALLBACK_PLAN, "intent": "none"},
            "products": [],
        }
    return {}


def node_load_catalog(state: ShoppingGraphState) -> dict[str, Any]:
    """Load package-local JSON catalog into state."""
    try:
        catalog = load_product_catalog()
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as e:
        logger.warning("catalog load failed: %s", e)
        return {
            "assistant_message": (
                "The shopping catalog is temporarily unavailable. "
                "Please try again later."
            ),
            "mode": "fallback",
            "preferences": {},
            "search_plan": _error_plan("error"),
            "products": [],
        }
    if not catalog:
        return {
            "assistant_message": (
                "The product catalog is empty; nothing to search yet."
            ),
            "mode": "fallback",
            "preferences": {},
            "search_plan": _error_plan("error"),
            "products": [],
        }
    return {"shopping_catalog": [p.to_serial() for p in catalog]}


def node_extract_preferences(state: ShoppingGraphState) -> dict[str, Any]:
    """Rule-based preference extraction."""
    catalog = [Product.from_serial(x) for x in state["shopping_catalog"]]
    msg = state["user_message"].strip()
    prefs = extract_preferences(msg, catalog)
    return {"preferences": prefs.to_public_dict()}


def node_retrieve_candidates(state: ShoppingGraphState) -> dict[str, Any]:
    """Filter + relax to build candidate product sets (retrieval)."""
    catalog = [Product.from_serial(x) for x in state["shopping_catalog"]]
    msg = state["user_message"].strip()
    prefs = preferences_from_public(state["preferences"])
    candidates, prefs, relaxed, retrieval_notes = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    return {
        "preferences": prefs.to_public_dict(),
        "shopping_relaxed": relaxed,
        "shopping_retrieval_notes": retrieval_notes,
        "shopping_candidates": [p.to_serial() for p in candidates],
    }


def node_rank_candidates(state: ShoppingGraphState) -> dict[str, Any]:
    """Score and order candidates."""
    candidates = [Product.from_serial(x) for x in state["shopping_candidates"]]
    msg = state["user_message"].strip()
    prefs = preferences_from_public(state["preferences"])
    ranked = rank_products(candidates, msg, prefs)[:8]
    ranked_top: list[dict[str, Any]] = []
    for p, sc in ranked:
        row = p.to_serial()
        row["relevance_score"] = round(sc, 2)
        ranked_top.append(row)
    return {"shopping_ranked": ranked_top}


def _search_plan_from_dict(d: dict[str, Any]) -> SearchPlan:
    hints = d.get("semantic_hints_by_product_type") or {}
    if not isinstance(hints, dict):
        hints = {}
    return SearchPlan(
        intent=str(d.get("intent", "")),
        filters_applied=list(d.get("filters_applied") or []),
        sort=str(d.get("sort", "")),
        relaxed=bool(d.get("relaxed", False)),
        match_quality=str(d.get("match_quality", "strong")),
        retrieval_notes=list(d.get("retrieval_notes") or []),
        product_types=list(d.get("product_types") or []),
        semantic_hints_by_product_type={str(k): list(v) for k, v in hints.items()},
        intent_category_defaults=list(d.get("intent_category_defaults") or []),
        normalized_categories=list(d.get("normalized_categories") or []),
        normalized_keywords=list(d.get("normalized_keywords") or []),
        facet_colors=list(d.get("facet_colors") or []),
        facet_style_keywords=list(d.get("facet_style_keywords") or []),
        facet_use_cases=list(d.get("facet_use_cases") or []),
        query_text_after_price_strip=str(d.get("query_text_after_price_strip") or ""),
        price_preference_summary=str(d.get("price_preference_summary") or ""),
    )


def node_build_search_plan(state: ShoppingGraphState) -> dict[str, Any]:
    """Attach structured search plan for clients and LLM context."""
    prefs = preferences_from_public(state["preferences"])
    ranked_raw = state.get("shopping_ranked") or []
    ranked_pairs: list[tuple[Product, float]] = []
    for raw in ranked_raw[:8]:
        sc = float(raw.get("relevance_score") or 0.0)
        body = {k: v for k, v in raw.items() if k != "relevance_score"}
        ranked_pairs.append((Product.from_serial(body), sc))
    notes = list(state.get("shopping_retrieval_notes") or [])
    match_quality = assess_match_quality(ranked_pairs, prefs, notes)
    catalog = [Product.from_serial(x) for x in state["shopping_catalog"]]
    plan = build_search_plan(
        state["user_message"].strip(),
        prefs,
        relaxed=bool(state.get("shopping_relaxed", False)),
        match_quality=match_quality,
        retrieval_notes=notes,
        catalog_categories=catalog_category_slugs(catalog),
    )
    return {"search_plan": plan.to_public_dict()}


def node_generate_response(state: ShoppingGraphState) -> dict[str, Any]:
    """Deterministic template reply, or LLM when configured and available."""
    ranked_raw = state.get("shopping_ranked") or []
    ranked_pairs: list[tuple[Product, float]] = []
    for raw in ranked_raw[:8]:
        sc = float(raw.get("relevance_score") or 0.0)
        body = {k: v for k, v in raw.items() if k != "relevance_score"}
        ranked_pairs.append((Product.from_serial(body), sc))

    prefs = preferences_from_public(state["preferences"])
    plan = _search_plan_from_dict(state.get("search_plan") or {})

    cards: list[dict[str, Any]] = []
    for p, sc in ranked_pairs[:5]:
        cards.append(_product_to_card(p, sc))

    det_reply = _format_reply(
        ranked_pairs,
        prefs,
        plan,
        relaxed=bool(state.get("shopping_relaxed", False)),
    )

    llm_text = try_generate_llm_reply(
        user_message=state["user_message"].strip(),
        preferences=state["preferences"],
        search_plan=state["search_plan"],
        product_cards=cards,
    )
    if llm_text:
        return {
            "assistant_message": llm_text,
            "mode": "llm",
            "products": cards,
        }
    return {
        "assistant_message": det_reply,
        "mode": "deterministic",
        "products": cards,
    }


def route_after_guard(state: ShoppingGraphState) -> str:
    if state.get("mode") == "fallback":
        return END
    return "load_catalog"


def route_after_load(state: ShoppingGraphState) -> str:
    if state.get("mode") == "fallback":
        return END
    return "extract_preferences"
