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

logger = logging.getLogger(__name__)


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
        "You are a shopping assistant. Answer using ONLY the product list below. "
        "Include product names and prices. "
        "If the list is empty, say you could not find matches and suggest "
        "how to refine the query. "
        "Do not invent products or prices."
    )
    payload = {
        "user_message": user_message,
        "extracted_preferences": preferences,
        "search_plan": search_plan,
        "ranked_products": product_cards,
    }
    human = (
        "Context (JSON):\n"
        f"{json.dumps(payload, indent=2)[:12000]}\n\n"
        "Write a short, helpful reply (under 12 sentences)."
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
) -> str | None:
    """Return LLM text or ``None`` if not configured or invocation fails."""
    if not shopping_chat_model_configured():
        return None
    try:
        return generate_llm_shopping_reply(
            user_message=user_message,
            preferences=preferences,
            search_plan=search_plan,
            product_cards=product_cards,
        )
    except Exception:
        logger.exception(
            "Shopping LLM reply failed; using deterministic reply instead"
        )
        return None
