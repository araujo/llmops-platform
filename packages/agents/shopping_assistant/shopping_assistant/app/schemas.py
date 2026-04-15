"""Pydantic models for shopping HTTP APIs (agent-owned)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ShoppingChatRequest(BaseModel):
    """Body for ``POST .../chat/shopping``."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        description="User message for the shopping turn.",
    )


class ProductCard(BaseModel):
    """One recommended product row returned to the client."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    price: float
    currency: str = "USD"
    category: str
    brand: str
    relevance_score: float | None = None


class ShoppingChatResponse(BaseModel):
    """Response for ``POST .../chat/shopping``."""

    model_config = ConfigDict(extra="forbid")

    reply: str = Field(..., description="Natural-language answer for this turn.")
    mode: Literal["deterministic", "llm", "fallback"] = Field(
        ...,
        description=(
            "deterministic: template reply from catalog; llm: model configured and "
            "succeeded; fallback: empty query or catalog issue."
        ),
    )
    preferences: dict[str, Any] | None = Field(
        default=None,
        description="Extracted preferences (budget, categories, brands, etc.).",
    )
    search_plan: dict[str, Any] | None = Field(
        default=None,
        description="How the query was interpreted (intent, filters, sort).",
    )
    products: list[ProductCard] = Field(
        default_factory=list,
        description="Ranked product recommendations (top matches).",
    )
