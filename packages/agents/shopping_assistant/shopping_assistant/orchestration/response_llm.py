"""Optional LLM reply generation owned by shopping assistant package."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from shopping_assistant.llm.factory import (
    create_shopping_chat_model,
    read_llm_settings_from_env,
)
from shopping_assistant.orchestration.pipeline_log import (
    PIPELINE_LOGGER,
    pipeline_stage_error,
)

logger = logging.getLogger(__name__)


def _grounding_block_for_product_count(n: int) -> str:
    """Human-message rules so the model cannot overstate catalog or capabilities."""
    if n == 0:
        return (
            "GROUNDING: ranked_products is empty. Say clearly that nothing "
            "from this catalog was returned for them. Suggest refining "
            "their request. Do not name or price any product."
        )
    if n == 1:
        return (
            "GROUNDING: ranked_products has EXACTLY ONE item. You may ONLY "
            "discuss that single product (use its name and price from the "
            "list). Do NOT say there are other options, styles, colors, or "
            "models available. Do NOT say 'we also have', 'check out our "
            "other', 'browse more', or 'additional Nike' (or any brand) "
            "items. Do NOT offer to show where items are in a physical "
            "store, aisle, shelf, inventory beyond this list, reviews, "
            "ratings, or to pull up more results—those capabilities are not "
            "available. Speak as if this one listing is the full answer."
        )
    return (
        f"GROUNDING: ranked_products has {n} items. Mention ONLY these "
        f"{n} products by name (and prices from the list). Do NOT imply a "
        "larger catalog, more styles, or other brands beyond these rows. "
        "Do NOT offer store directions, in-store pickup locations, reviews, "
        "or 'more results' unless you are comparing among the listed items "
        "only. If the user asked broadly, acknowledge these are the matches "
        "you have here—not a sample of a bigger inventory."
    )


def shopping_chat_model_configured() -> bool:
    try:
        return read_llm_settings_from_env() is not None
    except RuntimeError:
        # Partial config is treated as unconfigured for routing.
        return False


def generate_llm_shopping_reply(
    *,
    user_message: str,
    preferences: dict[str, Any],
    search_plan: dict[str, Any],
    product_cards: list[dict[str, Any]],
) -> str:
    """Grounded answer from ranked catalog rows (no invented SKUs)."""
    llm = create_shopping_chat_model()

    system = (
        "You are a concise shopping assistant. Your ONLY source of truth "
        "for what exists in this turn is the ranked_products array in the "
        "context. "
        "search_plan and extracted_preferences describe the query—they are "
        "NOT evidence of extra inventory; never claim products or variety "
        "beyond ranked_products. "
        "Use exact product names and prices from ranked_products only. "
        "Do not invent SKUs, deals, availability, or categories. "
        "Forbidden: implying more catalog items than listed; 'other styles' "
        "or 'more options' when only one product is listed; store layout, "
        "aisles, departments, reviews, ratings, or fetching more results. "
        "Do not mention JSON, scores, or internal machinery. "
        "Be natural and short (under 12 sentences)."
    )
    payload = {
        "user_message": user_message,
        "extracted_preferences": preferences,
        "search_plan": search_plan,
        "ranked_products": product_cards,
    }
    grounding = _grounding_block_for_product_count(len(product_cards))
    human = (
        "Use this context to answer (do not quote raw JSON in your reply):\n"
        f"{json.dumps(payload, indent=2)[:12000]}\n\n"
        f"{grounding}\n\n"
        "Write a short reply for the shopper following GROUNDING exactly."
    )
    msg = llm.invoke(
        [SystemMessage(content=system), HumanMessage(content=human)]
    )
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content.strip()
    return str(msg).strip()


def try_generate_llm_reply(
    *,
    user_message: str,
    preferences: dict[str, Any],
    search_plan: dict[str, Any],
    product_cards: list[dict[str, Any]],
    request_id: str | None = None,
) -> str | None:
    """Return LLM text or ``None`` if not configured or invocation fails."""
    mq = search_plan.get("match_quality")
    if mq in ("weak", "partial"):
        return None
    if not product_cards:
        return None
    if not shopping_chat_model_configured():
        return None
    try:
        return generate_llm_shopping_reply(
            user_message=user_message,
            preferences=preferences,
            search_plan=search_plan,
            product_cards=product_cards,
        )
    except Exception as exc:
        rid = request_id or "unknown"
        pipeline_stage_error(
            PIPELINE_LOGGER,
            "llm_generation",
            rid,
            exc,
            message_preview=(user_message or "")[:220],
        )
        logger.info(
            "Shopping LLM reply failed for request_id=%s; "
            "using deterministic reply instead",
            rid,
        )
        return None
