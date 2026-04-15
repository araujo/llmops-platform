"""HTTP routes for this agent (host mounts under ``/v1/agents/{agent_id}``)."""

from __future__ import annotations

import asyncio
from typing import Literal, cast

from fastapi import APIRouter

from shopping_assistant.app.schemas import ProductCard, ShoppingChatRequest, ShoppingChatResponse
from shopping_assistant.constants import AGENT_ID
from shopping_assistant.orchestration.graph import run_shopping_turn
from shopping_assistant.version import get_package_version


def build_agent_router() -> APIRouter:
    """Primary APIRouter for the shopping assistant agent."""
    router = APIRouter(tags=["shopping_assistant"])

    @router.get("/info")
    async def agent_info() -> dict[str, str]:
        """Lightweight agent metadata (no domain/business logic)."""
        return {
            "agent_id": AGENT_ID,
            "package_version": get_package_version(),
        }

    @router.post("/chat/shopping", response_model=ShoppingChatResponse)
    async def chat_shopping(body: ShoppingChatRequest) -> ShoppingChatResponse:
        """Run one shopping turn: deterministic catalog search, filter, and rank."""
        result = await asyncio.to_thread(run_shopping_turn, body.message)
        raw_products = result.get("products") or []
        products = [ProductCard(**p) for p in raw_products]
        m_raw = result.get("mode", "fallback")
        mode = cast(
            Literal["deterministic", "llm", "fallback"],
            m_raw if m_raw in ("deterministic", "llm", "fallback") else "fallback",
        )
        return ShoppingChatResponse(
            reply=result.get("assistant_message", ""),
            mode=mode,
            preferences=result.get("preferences"),
            search_plan=result.get("search_plan"),
            products=products,
        )

    return router
