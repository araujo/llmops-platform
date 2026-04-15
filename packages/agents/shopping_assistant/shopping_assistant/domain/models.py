"""Domain models for deterministic shopping (no FastAPI imports)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Product:
    """Catalog row (loaded from package-local JSON)."""

    id: str
    name: str
    category: str
    brand: str
    price: float
    currency: str
    tags: tuple[str, ...]
    colors: tuple[str, ...] = ()

    @classmethod
    def from_serial(cls, d: dict[str, Any]) -> Product:
        """Restore from graph state / JSON-like dict."""
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            category=str(d["category"]),
            brand=str(d["brand"]),
            price=float(d["price"]),
            currency=str(d.get("currency", "USD")),
            tags=tuple(d.get("tags") or ()),
            colors=tuple(d.get("colors") or ()),
        )

    def to_serial(self) -> dict[str, Any]:
        """Graph-safe dict (tuples as lists)."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "brand": self.brand,
            "price": self.price,
            "currency": self.currency,
            "tags": list(self.tags),
            "colors": list(self.colors),
        }

    def searchable_blob(self) -> str:
        parts = [
            self.name,
            self.category,
            self.brand,
            " ".join(self.tags),
            " ".join(self.colors),
        ]
        return " ".join(parts).lower()


@dataclass(slots=True)
class UserPreferences:
    """Heuristic extraction from the user message (deterministic)."""

    max_price: float | None = None
    min_price: float | None = None
    categories: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    product_types: list[str] = field(default_factory=list)
    style_keywords: list[str] = field(default_factory=list)
    gift_intent: bool = False
    keywords: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "max_price": self.max_price,
            "min_price": self.min_price,
            "categories": list(self.categories),
            "brands": list(self.brands),
            "colors": list(self.colors),
            "use_cases": list(self.use_cases),
            "product_types": list(self.product_types),
            "style_keywords": list(self.style_keywords),
            "gift_intent": self.gift_intent,
            "keywords": list(self.keywords),
        }


@dataclass(slots=True)
class SearchPlan:
    """Explains how we interpreted the query before filter/rank."""

    intent: str
    filters_applied: list[str]
    sort: str
    relaxed: bool = False
    match_quality: str = "strong"
    retrieval_notes: list[str] = field(default_factory=list)
    # Semantic plan layer (API / observability; not wired into retrieval yet).
    product_types: list[str] = field(default_factory=list)
    semantic_hints_by_product_type: dict[str, list[str]] = field(
        default_factory=dict
    )
    intent_category_defaults: list[str] = field(default_factory=list)
    normalized_categories: list[str] = field(default_factory=list)
    normalized_keywords: list[str] = field(default_factory=list)
    facet_colors: list[str] = field(default_factory=list)
    facet_style_keywords: list[str] = field(default_factory=list)
    facet_use_cases: list[str] = field(default_factory=list)
    query_text_after_price_strip: str = ""
    price_preference_summary: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "filters_applied": list(self.filters_applied),
            "sort": self.sort,
            "relaxed": self.relaxed,
            "match_quality": self.match_quality,
            "retrieval_notes": list(self.retrieval_notes),
            "product_types": list(self.product_types),
            "semantic_hints_by_product_type": dict(
                self.semantic_hints_by_product_type
            ),
            "intent_category_defaults": list(self.intent_category_defaults),
            "normalized_categories": list(self.normalized_categories),
            "normalized_keywords": list(self.normalized_keywords),
            "facet_colors": list(self.facet_colors),
            "facet_style_keywords": list(self.facet_style_keywords),
            "facet_use_cases": list(self.facet_use_cases),
            "query_text_after_price_strip": self.query_text_after_price_strip,
            "price_preference_summary": self.price_preference_summary,
        }


@dataclass(slots=True)
class DeterministicTurnResult:
    """One turn output for the graph / HTTP layer."""

    reply: str
    mode: str  # "deterministic" | "llm" | "fallback"
    preferences: dict[str, Any]
    search_plan: dict[str, Any]
    products: list[dict[str, Any]]


def preferences_from_public(d: dict[str, Any]) -> UserPreferences:
    """Rebuild :class:`UserPreferences` from public dict (graph handoff)."""
    return UserPreferences(
        max_price=d.get("max_price"),
        min_price=d.get("min_price"),
        categories=list(d.get("categories") or []),
        brands=list(d.get("brands") or []),
        colors=list(d.get("colors") or []),
        use_cases=list(d.get("use_cases") or []),
        product_types=list(d.get("product_types") or []),
        style_keywords=list(d.get("style_keywords") or []),
        gift_intent=bool(d.get("gift_intent", False)),
        keywords=list(d.get("keywords") or []),
    )
