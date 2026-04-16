"""LangGraph node functions for the shopping pipeline.

Logic lives in this package only.
"""

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
from shopping_assistant.orchestration.pipeline_log import (
    PIPELINE_LOGGER,
    compact_preferences,
    compact_state_summary,
    pipeline_event,
    pipeline_stage_error,
)
from shopping_assistant.orchestration.response_llm import (
    shopping_chat_model_configured,
    try_generate_llm_reply,
)
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


def _request_id(state: ShoppingGraphState) -> str:
    return str(state.get("shopping_request_id") or "unknown")


def _short_label(text: str, max_len: int = 36) -> str:
    t = text.replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


def _prefs_log_fields(prefs_dict: dict[str, Any]) -> dict[str, Any]:
    """Scalar/list fields for stage logs (short)."""
    return {
        "brands": list(prefs_dict.get("brands") or [])[:12],
        "product_types": list(prefs_dict.get("product_types") or [])[:12],
        "colors": list(prefs_dict.get("colors") or [])[:12],
    }


def _fallback_search_plan(state: ShoppingGraphState) -> dict[str, Any]:
    """Minimal plan when plan generation fails (downstream still valid)."""
    prefs = state.get("preferences") or {}
    return SearchPlan(
        intent="error",
        filters_applied=[],
        sort="n/a",
        relaxed=bool(state.get("shopping_relaxed", False)),
        match_quality="weak",
        retrieval_notes=list(state.get("shopping_retrieval_notes") or []),
        product_types=list(prefs.get("product_types") or []),
        normalized_categories=[],
    ).to_public_dict()


def _response_build_error(
    state: ShoppingGraphState,
    exc: Exception,
) -> dict[str, Any]:
    summary = compact_state_summary(state)
    pipeline_stage_error(
        PIPELINE_LOGGER,
        "generate_response",
        _request_id(state),
        exc,
        state_summary=summary,
    )
    return {
        "assistant_message": (
            "Something went wrong while preparing your shopping reply. "
            "Please try again in a moment."
        ),
        "mode": "fallback",
        "products": [],
    }


def node_guard_input(state: ShoppingGraphState) -> dict[str, Any]:
    """Reject empty user input."""
    msg = (state.get("user_message") or "").strip()
    if not msg:
        pipeline_event(
            PIPELINE_LOGGER,
            "guard_reject",
            _request_id(state),
            reason="empty_message",
        )
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
        pipeline_event(
            PIPELINE_LOGGER,
            "catalog_load_failed",
            _request_id(state),
            error=str(e)[:120],
        )
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
        pipeline_event(
            PIPELINE_LOGGER,
            "catalog_empty",
            _request_id(state),
        )
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
    rid = _request_id(state)
    try:
        catalog = [Product.from_serial(x) for x in state["shopping_catalog"]]
        msg = state["user_message"].strip()
        prefs = extract_preferences(msg, catalog)
        prefs_dict = prefs.to_public_dict()
        plog = _prefs_log_fields(prefs_dict)
        pipeline_event(
            PIPELINE_LOGGER,
            "preferences_extracted",
            rid,
            message=msg[:400],
            preferences=compact_preferences(prefs_dict),
            **plog,
        )
        return {"preferences": prefs_dict}
    except Exception as exc:
        pipeline_stage_error(
            PIPELINE_LOGGER,
            "extract_preferences",
            rid,
            exc,
            state_summary=compact_state_summary(state),
        )
        return {"preferences": {}}


def node_retrieve_candidates(state: ShoppingGraphState) -> dict[str, Any]:
    """Filter + relax to build candidate product sets (retrieval)."""
    rid = _request_id(state)
    try:
        catalog = [Product.from_serial(x) for x in state["shopping_catalog"]]
        msg = state["user_message"].strip()
        prefs = preferences_from_public(state["preferences"])
        (
            candidates,
            prefs,
            relaxed,
            retrieval_notes,
        ) = retrieve_candidates_with_relaxation(catalog, msg, prefs=prefs)
        pd = prefs.to_public_dict()
        plog = _prefs_log_fields(pd)
        pipeline_event(
            PIPELINE_LOGGER,
            "retrieval_done",
            rid,
            message=msg[:400],
            candidate_count=len(candidates),
            relaxed=relaxed,
            shopping_relaxed=relaxed,
            retrieval_notes_n=len(retrieval_notes),
            **plog,
        )
        return {
            "preferences": pd,
            "shopping_relaxed": relaxed,
            "shopping_retrieval_notes": retrieval_notes,
            "shopping_candidates": [p.to_serial() for p in candidates],
        }
    except Exception as exc:
        pipeline_stage_error(
            PIPELINE_LOGGER,
            "retrieve_candidates",
            rid,
            exc,
            state_summary=compact_state_summary(state),
        )
        base_prefs = state.get("preferences") or {}
        return {
            "preferences": base_prefs,
            "shopping_relaxed": False,
            "shopping_retrieval_notes": [],
            "shopping_candidates": [],
        }


def node_rank_candidates(state: ShoppingGraphState) -> dict[str, Any]:
    """Score and order candidates."""
    rid = _request_id(state)
    try:
        candidates = [
            Product.from_serial(x) for x in state["shopping_candidates"]
        ]
        msg = state["user_message"].strip()
        prefs = preferences_from_public(state["preferences"])
        ranked = rank_products(candidates, msg, prefs)[:8]
        ranked_top: list[dict[str, Any]] = []
        for p, sc in ranked:
            row = p.to_serial()
            row["relevance_score"] = round(sc, 2)
            ranked_top.append(row)
        tops = [
            f"{p.id}|{_short_label(p.name)}|{round(sc, 2)}"
            for p, sc in ranked[:5]
        ]
        pd = state.get("preferences") or {}
        plog = _prefs_log_fields(pd)
        pipeline_event(
            PIPELINE_LOGGER,
            "ranking_done",
            rid,
            message=msg[:400],
            ranked_count=len(ranked_top),
            candidate_in=len(candidates),
            top_ranked=tops,
            **plog,
        )
        return {"shopping_ranked": ranked_top}
    except Exception as exc:
        pipeline_stage_error(
            PIPELINE_LOGGER,
            "rank_candidates",
            rid,
            exc,
            state_summary=compact_state_summary(state),
        )
        return {"shopping_ranked": []}


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
    rid = _request_id(state)
    try:
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
        sp = plan.to_public_dict()
        pd = state.get("preferences") or {}
        plog = _prefs_log_fields(pd)
        msg = state["user_message"].strip()
        pipeline_event(
            PIPELINE_LOGGER,
            "search_plan_ready",
            rid,
            message=msg[:400],
            intent=sp.get("intent"),
            match_quality=sp.get("match_quality"),
            relaxed=sp.get("relaxed"),
            normalized_categories=sp.get("normalized_categories"),
            filters_n=len(sp.get("filters_applied") or []),
            product_types=sp.get("product_types"),
            **plog,
        )
        return {"search_plan": sp}
    except Exception as exc:
        pipeline_stage_error(
            PIPELINE_LOGGER,
            "build_search_plan",
            rid,
            exc,
            state_summary=compact_state_summary(state),
        )
        return {"search_plan": _fallback_search_plan(state)}


def node_generate_response(state: ShoppingGraphState) -> dict[str, Any]:
    """Deterministic template reply, or LLM when configured and available."""
    rid = _request_id(state)
    try:
        return _node_generate_response_impl(state, rid)
    except Exception as exc:
        return _response_build_error(state, exc)


def _node_generate_response_impl(
    state: ShoppingGraphState,
    rid: str,
) -> dict[str, Any]:
    msg = state["user_message"].strip()
    ranked_raw = state.get("shopping_ranked") or []
    ranked_pairs: list[tuple[Product, float]] = []
    for raw in ranked_raw[:8]:
        sc = float(raw.get("relevance_score") or 0.0)
        body = {k: v for k, v in raw.items() if k != "relevance_score"}
        ranked_pairs.append((Product.from_serial(body), sc))

    prefs = preferences_from_public(state["preferences"])
    plan = _search_plan_from_dict(state.get("search_plan") or {})

    mq = plan.match_quality
    if mq == "weak":
        reply_pairs: list[tuple[Product, float]] = []
        cards: list[dict[str, Any]] = []
    else:
        reply_pairs = ranked_pairs[:5]
        cards = [_product_to_card(p, sc) for p, sc in reply_pairs]

    det_reply = _format_reply(
        reply_pairs,
        prefs,
        plan,
        relaxed=bool(state.get("shopping_relaxed", False)),
    )

    sp_dict = state.get("search_plan") or {}
    mq_raw = sp_dict.get("match_quality")
    skip_reason: str | None
    if mq_raw in ("weak", "partial"):
        skip_reason = "match_quality_tier"
    elif not cards:
        skip_reason = "no_product_cards"
    elif not shopping_chat_model_configured():
        skip_reason = "llm_not_configured"
    else:
        skip_reason = None
    pd = state.get("preferences") or {}
    plog = _prefs_log_fields(pd)
    pipeline_event(
        PIPELINE_LOGGER,
        "llm_gate",
        rid,
        message=msg[:400],
        match_quality=mq_raw,
        relaxed=state.get("shopping_relaxed"),
        product_cards=len(cards),
        llm_configured=shopping_chat_model_configured(),
        will_attempt_llm=skip_reason is None,
        llm_skip_reason=skip_reason or "none",
        normalized_categories=(sp_dict.get("normalized_categories")),
        **plog,
    )

    pipeline_event(
        PIPELINE_LOGGER,
        "before_response",
        rid,
        message=msg[:400],
        path=("llm" if skip_reason is None else "deterministic_template"),
        match_quality=mq_raw,
        product_cards=len(cards),
    )

    llm_text = try_generate_llm_reply(
        user_message=msg,
        preferences=state["preferences"],
        search_plan=state["search_plan"],
        product_cards=cards,
        request_id=rid,
    )
    if llm_text:
        pipeline_event(
            PIPELINE_LOGGER,
            "response_final",
            rid,
            message=msg[:400],
            mode="llm",
            llm_used=True,
            products_shown=len(cards),
            reply_chars=len(llm_text),
            match_quality=mq_raw,
        )
        return {
            "assistant_message": llm_text,
            "mode": "llm",
            "products": cards,
        }
    pipeline_event(
        PIPELINE_LOGGER,
        "response_final",
        rid,
        message=msg[:400],
        mode="deterministic",
        llm_used=False,
        products_shown=len(cards),
        reply_chars=len(det_reply),
        match_quality=mq_raw,
    )
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
