"""Deterministic search / filter / rank over the package-local product catalog."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from importlib import resources
from typing import Any

from shopping_assistant.domain.models import (
    DeterministicTurnResult,
    Product,
    SearchPlan,
    UserPreferences,
)


def retrieve_candidates_with_relaxation(
    catalog: list[Product],
    text: str,
    *,
    prefs: UserPreferences | None = None,
) -> tuple[list[Product], UserPreferences, bool, list[str]]:
    """Retrieve candidates with deterministic filters + lexical refinement.

    Returns ``(candidates, prefs, relaxed, retrieval_notes)``. Notes explain any
    constraint relaxation for transparent fallback messaging (grounded, no LLM).
    """
    if prefs is None:
        prefs = extract_preferences(text, catalog)
    relaxed = False
    strict_colors = True
    retrieval_notes: list[str] = []
    candidates = retrieve_candidates(
        catalog,
        text,
        prefs,
        strict_colors=strict_colors,
    )
    if not candidates and not prefs.categories and prefs.product_types:
        nearest = infer_nearest_categories_from_types(catalog, prefs)
        if nearest:
            relaxed = True
            retrieval_notes.append(
                "Mapped your request to the closest available categories in this catalog."
            )
            near_prefs = _copy_prefs(prefs, categories=nearest)
            candidates = retrieve_candidates(
                catalog,
                text,
                near_prefs,
                strict_colors=strict_colors,
            )
            if candidates:
                prefs = near_prefs
    if not candidates and prefs.colors:
        strict_colors = False
        relaxed = True
        retrieval_notes.append(
            "Relaxed the color filter so more catalog items can be considered."
        )
        candidates = retrieve_candidates(catalog, text, prefs, strict_colors=False)
    if not candidates and prefs.max_price is not None:
        relaxed = True
        wide = _copy_prefs(
            prefs,
            max_price=prefs.max_price * 1.25,
            colors=[],
        )
        retrieval_notes.append(
            f"Widened the budget ceiling to about ${wide.max_price:g} (from your limit)."
        )
        candidates = retrieve_candidates(catalog, text, wide, strict_colors=False)
        prefs = wide
    if not candidates:
        relaxed = True
        candidates = _lexical_refine_candidates(catalog, text, prefs)
        if not candidates:
            candidates = list(catalog)
            retrieval_notes.append(
                "No exact filter match; ranked the full catalog for the closest items."
            )
        else:
            retrieval_notes.append(
                "No exact filter match; took the closest lexical matches from the catalog."
            )
    return candidates, prefs, relaxed, retrieval_notes

logger = logging.getLogger(__name__)

_CATALOG_CACHE: list[Product] | None = None

# Keywords (message substring) -> canonical category slug (matches JSON ``category``).
# Only hints that map to a real ``category`` value in the loaded catalog are applied
# (see ``infer_catalog_categories``).
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "headphones": ("headphone", "over-ear", "over ear", "anc", "noise cancel"),
    "earbuds": ("earbud", "ear bud", "airpods", "galaxy buds", "buds"),
    "laptops": ("laptop", "macbook", "thinkpad", "xps", "notebook", "ultrabook"),
    "e-readers": ("kindle", "e-reader", "ebook", "e book"),
    "kitchen": ("blender", "instant pot", "cooker", "pressure cook", "ninja"),
    "accessories": ("keyboard", "charger", "usb-c", "usb c", "charging"),
}

# Multi-word phrases (longer first) -> candidate catalog ``category`` slugs, in priority order.
# Intersection with the live catalog decides what is actually used for retrieval.
PHRASE_TO_CATEGORY_CANDIDATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("work bag", ("bags", "handbags", "tote", "satchel", "briefcase", "accessories")),
    ("office bag", ("bags", "handbags", "tote", "satchel", "accessories")),
    ("gym bag", ("bags", "handbags", "tote", "accessories")),
    ("running shoes", ("shoes", "athletic shoes", "footwear", "sneakers")),
    ("athletic shoes", ("shoes", "athletic shoes", "footwear", "sneakers")),
)

# Product-type keys (from ``PRODUCT_TYPE_KEYWORDS``) -> candidate catalog slugs.
PRODUCT_TYPE_TO_CATEGORY_CANDIDATES: dict[str, tuple[str, ...]] = {
    # Footwear / athletic
    "sneakers": (
        "shoes",
        "athletic shoes",
        "footwear",
        "sneakers",
        "trainers",
    ),
    # Bags / carry
    "bag": (
        "bags",
        "handbags",
        "handbag",
        "tote",
        "satchel",
        "briefcase",
        "office bag",
        "accessories",
    ),
    # Fragrance / beauty
    "perfume": (
        "perfume",
        "fragrance",
        "beauty",
        "personal care",
        "cologne",
    ),
}

# Single-token synonyms -> candidate catalog slugs (matched on word boundaries in the message).
TOKEN_TO_CATEGORY_CANDIDATES: dict[str, tuple[str, ...]] = {
    "sneaker": ("shoes", "athletic shoes", "footwear", "sneakers"),
    "sneakers": ("shoes", "athletic shoes", "footwear", "sneakers"),
    "trainers": ("shoes", "footwear", "sneakers"),
    "trainer": ("shoes", "footwear", "sneakers"),
    "footwear": ("shoes", "footwear", "sneakers"),
    "handbag": ("bags", "handbags", "handbag", "tote"),
    "handbags": ("bags", "handbags", "tote"),
    "tote": ("bags", "handbags", "tote"),
    "satchel": ("bags", "handbags", "satchel"),
    "briefcase": ("bags", "briefcase", "accessories"),
    "fragrance": ("fragrance", "perfume", "beauty"),
    "cologne": ("fragrance", "perfume", "beauty"),
    "perfume": ("perfume", "fragrance", "beauty"),
}

_COLOR_WORDS = frozenset(
    {
        "black",
        "white",
        "silver",
        "gray",
        "grey",
        "blue",
        "green",
        "red",
        "pink",
        "brown",
        "beige",
        "navy",
        "gold",
        "graphite",
        "midnight",
        "platinum",
        "stainless",
    }
)

USE_CASE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "work": ("work", "office", "business", "professional"),
    "travel": ("travel", "trip", "vacation", "carry-on", "carry on"),
    "fitness": ("gym", "running", "workout", "training", "sports"),
    "commute": ("commute", "commuting"),
}

PRODUCT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sneakers": ("sneaker", "sneakers", "trainers", "running shoes"),
    "perfume": ("perfume", "fragrance", "cologne"),
    "bag": ("bag", "backpack", "tote", "briefcase", "crossbody"),
    "headphones": ("headphones", "headphone"),
    "earbuds": ("earbuds", "earbud"),
    "laptop": ("laptop", "notebook", "ultrabook"),
}

STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "casual": ("casual",),
    "formal": ("formal", "professional"),
    "sporty": ("sporty", "athletic"),
    "minimal": ("minimal", "minimalist"),
    "luxury": ("luxury", "premium", "high-end", "high end"),
    "elegant": ("elegant", "classic"),
}

_GIFT_WORDS = ("gift", "present", "birthday", "anniversary", "for him", "for her")

_KEYWORD_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "under",
        "over",
        "below",
        "above",
        "dollars",
        "dollar",
        "need",
        "find",
        "show",
        "gift",
        "work",
    }
)

# Tunable deterministic ranking weights.
RANK_WEIGHTS: dict[str, float] = {
    "lexical_token_match": 1.4,
    "keyword_match": 1.1,
    "category_match": 4.5,
    "brand_match": 3.2,
    "color_match": 2.2,
    "product_type_match": 2.0,
    "use_case_match": 1.1,
    "style_match": 0.9,
    "price_fit_strong": 2.2,
    "price_fit_near": 1.0,
    "price_fit_out_of_range": -1.5,
}

# Below this rank score, structured queries are treated as weak matches for messaging.
WEAK_MATCH_SCORE_THRESHOLD = 7.5


def _load_catalog_raw() -> list[dict[str, Any]]:
    pkg = resources.files("shopping_assistant.data.samples")
    raw = pkg.joinpath("products.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("catalog root must be a list")
    return data


def load_product_catalog() -> list[Product]:
    """Load and cache products from ``data/samples/products.json``."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    rows = _load_catalog_raw()
    out: list[Product] = []
    for row in rows:
        out.append(
            Product(
                id=str(row["id"]),
                name=str(row["name"]),
                category=str(row["category"]),
                brand=str(row["brand"]),
                price=float(row["price"]),
                currency=str(row.get("currency", "USD")),
                tags=tuple(row.get("tags") or ()),
                colors=tuple(row.get("colors") or ()),
            )
        )
    _CATALOG_CACHE = out
    return out


def known_brands_from_catalog(products: Sequence[Product]) -> list[str]:
    brands = {p.brand.strip() for p in products if p.brand.strip()}
    return sorted(brands, key=len, reverse=True)


def catalog_category_slugs(products: Sequence[Product]) -> frozenset[str]:
    """Distinct ``Product.category`` values from the loaded catalog."""
    return frozenset(p.category for p in products if getattr(p, "category", ""))


def _pick_present(
    candidates: tuple[str, ...], catalog_categories: frozenset[str]
) -> list[str]:
    return [c for c in candidates if c in catalog_categories]


def infer_catalog_categories(
    message_lower: str,
    prefs: UserPreferences,
    catalog_categories: frozenset[str],
) -> list[str]:
    """Map user language to catalog ``category`` slugs present in the live catalog.

    Order is stable and explainable: keyword hints, multi-word phrases, product
    types, then single-token synonyms.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add_many(cands: Iterable[str]) -> None:
        for c in cands:
            if c in catalog_categories and c not in seen:
                seen.add(c)
                out.append(c)

    for cat_slug, hints in CATEGORY_KEYWORDS.items():
        if cat_slug not in catalog_categories:
            continue
        if any(h in message_lower for h in hints):
            add_many([cat_slug])

    for phrase, candidates in PHRASE_TO_CATEGORY_CANDIDATES:
        if phrase in message_lower:
            add_many(_pick_present(candidates, catalog_categories))

    for pt in prefs.product_types:
        cands = PRODUCT_TYPE_TO_CATEGORY_CANDIDATES.get(pt)
        if cands:
            add_many(_pick_present(cands, catalog_categories))

    for token, candidates in TOKEN_TO_CATEGORY_CANDIDATES.items():
        if re.search(rf"\b{re.escape(token)}\b", message_lower):
            add_many(_pick_present(candidates, catalog_categories))

    return out


def extract_preferences(message: str, products: list[Product]) -> UserPreferences:
    """Rule-based preference extraction (no LLM)."""
    text = message.strip()
    lower = text.lower()
    prefs = UserPreferences()

    for m in re.finditer(
        r"(?:under|below|less than|max(?:imum)?|at most)\s*\$?\s*(\d+(?:\.\d+)?)",
        lower,
    ):
        prefs.max_price = float(m.group(1))
    for m in re.finditer(
        r"(?:over|above|at least|min(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)",
        lower,
    ):
        prefs.min_price = float(m.group(1))

    # "between 50 and 100", "$50-$100", "50 to 100 dollars"
    range_patterns = (
        r"(?:between)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:and|to)\s*\$?\s*(\d+(?:\.\d+)?)",
        r"\$?\s*(\d+(?:\.\d+)?)\s*[-–]\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|usd)?",
    )
    for pat in range_patterns:
        m = re.search(pat, lower)
        if not m:
            continue
        a, b = float(m.group(1)), float(m.group(2))
        prefs.min_price = min(a, b)
        prefs.max_price = max(a, b)
        break

    if re.search(r"\b(cheap|budget|affordable|inexpensive)\b", lower):
        if prefs.max_price is None:
            prefs.max_price = 75.0

    for use_case, hints in USE_CASE_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(h)}\b", lower) for h in hints):
            if use_case not in prefs.use_cases:
                prefs.use_cases.append(use_case)

    for product_type, hints in PRODUCT_TYPE_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(h)}\b", lower) for h in hints):
            if product_type not in prefs.product_types:
                prefs.product_types.append(product_type)

    for style, hints in STYLE_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(h)}\b", lower) for h in hints):
            if style not in prefs.style_keywords:
                prefs.style_keywords.append(style)

    if any(w in lower for w in _GIFT_WORDS):
        prefs.gift_intent = True

    for brand in known_brands_from_catalog(products):
        if re.search(rf"\b{re.escape(brand.lower())}\b", lower):
            if brand not in prefs.brands:
                prefs.brands.append(brand)

    for c in _COLOR_WORDS:
        if re.search(rf"\b{re.escape(c)}\b", lower):
            prefs.colors.append(c)

    for token in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", lower):
        if token in _COLOR_WORDS or token in _KEYWORD_STOPWORDS:
            continue
        if token not in prefs.keywords:
            prefs.keywords.append(token)

    catalog_cats = catalog_category_slugs(products)
    prefs.categories = infer_catalog_categories(lower, prefs, catalog_cats)
    return prefs


def _has_structured_intent(prefs: UserPreferences) -> bool:
    return bool(
        prefs.categories
        or prefs.brands
        or prefs.product_types
        or prefs.use_cases
        or prefs.colors
        or prefs.max_price is not None
        or prefs.min_price is not None
    )


def _product_matches_product_types(p: Product, prefs: UserPreferences) -> bool:
    if not prefs.product_types:
        return True
    blob = p.searchable_blob()
    return any(
        any(hint in blob for hint in PRODUCT_TYPE_KEYWORDS.get(pt, ()))
        for pt in prefs.product_types
    )


def assess_match_quality(
    ranked: list[tuple[Product, float]],
    prefs: UserPreferences,
    retrieval_notes: list[str],
) -> str:
    """Label match strength for grounded fallback copy (``strong`` or ``weak``)."""
    if not ranked:
        return "weak"
    if not _has_structured_intent(prefs):
        return "strong"
    top_p, top_s = ranked[0]
    if prefs.product_types and not _product_matches_product_types(top_p, prefs):
        return "weak"
    if top_s < WEAK_MATCH_SCORE_THRESHOLD:
        return "weak"
    if any("full catalog" in n.lower() for n in retrieval_notes) and top_s < 11.0:
        return "weak"
    return "strong"


def build_search_plan(
    message: str,
    prefs: UserPreferences,
    *,
    relaxed: bool,
    match_quality: str = "strong",
    retrieval_notes: list[str] | None = None,
) -> SearchPlan:
    filters: list[str] = []
    if prefs.max_price is not None:
        filters.append(f"price <= {prefs.max_price:g}")
    if prefs.min_price is not None:
        filters.append(f"price >= {prefs.min_price:g}")
    if prefs.categories:
        filters.append(f"category in {prefs.categories}")
    if prefs.brands:
        filters.append(f"brand in {prefs.brands}")
    if prefs.colors:
        filters.append(f"color in {prefs.colors}")

    intent = "find_products"
    if not any(
        (
            prefs.categories,
            prefs.brands,
            prefs.max_price is not None,
            prefs.keywords,
        )
    ):
        intent = "browse_or_explore"

    return SearchPlan(
        intent=intent,
        filters_applied=filters,
        sort="relevance_then_price",
        relaxed=relaxed,
        match_quality=match_quality,
        retrieval_notes=list(retrieval_notes or []),
    )


def _matches_color(p: Product, colors: list[str]) -> bool:
    if not colors:
        return True
    plc = {c.lower() for c in p.colors}
    return bool(plc.intersection(c.lower() for c in colors))


def _copy_prefs(
    prefs: UserPreferences,
    *,
    max_price: float | None | object = ...,
    min_price: float | None | object = ...,
    categories: list[str] | object = ...,
    brands: list[str] | object = ...,
    colors: list[str] | object = ...,
    use_cases: list[str] | object = ...,
    product_types: list[str] | object = ...,
    style_keywords: list[str] | object = ...,
    gift_intent: bool | object = ...,
    keywords: list[str] | object = ...,
) -> UserPreferences:
    """Clone preferences while overriding selected fields."""
    return UserPreferences(
        max_price=prefs.max_price if max_price is ... else max_price,
        min_price=prefs.min_price if min_price is ... else min_price,
        categories=list(prefs.categories if categories is ... else categories),
        brands=list(prefs.brands if brands is ... else brands),
        colors=list(prefs.colors if colors is ... else colors),
        use_cases=list(prefs.use_cases if use_cases is ... else use_cases),
        product_types=list(
            prefs.product_types if product_types is ... else product_types
        ),
        style_keywords=list(
            prefs.style_keywords if style_keywords is ... else style_keywords
        ),
        gift_intent=prefs.gift_intent if gift_intent is ... else gift_intent,
        keywords=list(prefs.keywords if keywords is ... else keywords),
    )


def infer_nearest_categories_from_types(
    products: list[Product],
    prefs: UserPreferences,
) -> list[str]:
    """Choose nearest catalog categories using product-type lexical overlap."""
    if prefs.categories or not prefs.product_types:
        return []
    category_scores: dict[str, float] = {}
    for category in catalog_category_slugs(products):
        score = 0.0
        cat_products = [p for p in products if p.category == category]
        cat_blob = " ".join([category] + [p.searchable_blob() for p in cat_products])
        for product_type in prefs.product_types:
            for hint in PRODUCT_TYPE_KEYWORDS.get(product_type, ()):
                if hint in cat_blob:
                    score += 1.0
        if score > 0:
            category_scores[category] = score
    return [
        c
        for c, _ in sorted(category_scores.items(), key=lambda x: (-x[1], x[0]))[:2]
    ]


def _lexical_retrieval_score(
    product: Product,
    message: str,
    prefs: UserPreferences,
) -> float:
    blob = product.searchable_blob()
    lower = message.lower()
    msg_tokens = [t for t in re.findall(r"[a-z0-9]+", lower) if len(t) >= 3]
    score = 0.0

    for token in msg_tokens:
        if token in blob:
            score += 1.2
    for kw in prefs.keywords:
        if kw in blob:
            score += 1.0
    for pt in prefs.product_types:
        for hint in PRODUCT_TYPE_KEYWORDS.get(pt, ()):
            if hint in blob:
                score += 1.8
    for use_case in prefs.use_cases:
        for hint in USE_CASE_KEYWORDS.get(use_case, ()):
            if hint in blob:
                score += 0.8
    if prefs.categories and product.category in prefs.categories:
        score += 3.0
    if prefs.brands and any(b.lower() in product.brand.lower() for b in prefs.brands):
        score += 2.5
    if prefs.colors and _matches_color(product, prefs.colors):
        score += 1.0
    if prefs.max_price is not None and product.price <= prefs.max_price:
        score += 0.4
    if prefs.min_price is not None and product.price >= prefs.min_price:
        score += 0.4
    return score


def _lexical_refine_candidates(
    products: list[Product],
    message: str,
    prefs: UserPreferences,
) -> list[Product]:
    """Keep a relevant subset before ranking, but never return empty here."""
    if not products:
        return []
    scored = [(p, _lexical_retrieval_score(p, message, prefs)) for p in products]
    positives = [(p, sc) for p, sc in scored if sc > 0]
    if positives:
        positives.sort(key=lambda x: (-x[1], x[0].price))
        keep = min(max(5, len(positives)), 20)
        return [p for p, _ in positives[:keep]]
    scored.sort(key=lambda x: (-x[1], x[0].price))
    return [p for p, _ in scored[: min(len(scored), 10)]]


def retrieve_candidates(
    products: list[Product],
    message: str,
    prefs: UserPreferences,
    *,
    strict_colors: bool,
) -> list[Product]:
    """Deterministic candidate retrieval: hard filters then lexical refinement."""
    base = filter_products(products, prefs, strict_colors=strict_colors)
    if not base:
        return []
    return _lexical_refine_candidates(base, message, prefs)


def filter_products(
    products: list[Product],
    prefs: UserPreferences,
    *,
    strict_colors: bool,
) -> list[Product]:
    out: list[Product] = []
    for p in products:
        if prefs.max_price is not None and p.price > prefs.max_price + 0.005:
            continue
        if prefs.min_price is not None and p.price < prefs.min_price - 0.005:
            continue
        if prefs.categories and p.category not in prefs.categories:
            continue
        if prefs.brands:
            if p.brand not in prefs.brands:
                continue
        if strict_colors and prefs.colors and not _matches_color(p, prefs.colors):
            continue
        out.append(p)
    return out


def rank_products(
    candidates: list[Product],
    message: str,
    prefs: UserPreferences,
) -> list[tuple[Product, float]]:
    """Return (product, score) sorted by score descending.

    Score composition is deterministic and explainable:
    - lexical relevance (message tokens + extracted keywords)
    - explicit preference matches (category, brand, color)
    - intent attributes (product type, use case, style)
    - price fit (inside range, near budget, or clearly out of range)
    """
    lower = message.lower()
    msg_tokens = {t for t in re.findall(r"[a-z0-9]+", lower) if len(t) >= 3}
    scored: list[tuple[Product, float]] = []
    for p in candidates:
        blob = p.searchable_blob()
        s = 0.0
        for w in msg_tokens:
            if w in blob:
                s += RANK_WEIGHTS["lexical_token_match"]
        for kw in prefs.keywords:
            if kw in blob:
                s += RANK_WEIGHTS["keyword_match"]
        if prefs.categories and p.category in prefs.categories:
            s += RANK_WEIGHTS["category_match"]
        for b in prefs.brands:
            if b.lower() in p.brand.lower():
                s += RANK_WEIGHTS["brand_match"]
        if prefs.colors:
            if _matches_color(p, prefs.colors):
                s += RANK_WEIGHTS["color_match"]

        for pt in prefs.product_types:
            if any(hint in blob for hint in PRODUCT_TYPE_KEYWORDS.get(pt, ())):
                s += RANK_WEIGHTS["product_type_match"]
        for use_case in prefs.use_cases:
            if any(hint in blob for hint in USE_CASE_KEYWORDS.get(use_case, ())):
                s += RANK_WEIGHTS["use_case_match"]
        for style in prefs.style_keywords:
            if any(hint in blob for hint in STYLE_KEYWORDS.get(style, ())):
                s += RANK_WEIGHTS["style_match"]

        s += _price_fit_score(p.price, prefs)
        scored.append((p, s))
    scored.sort(key=lambda x: (-x[1], x[0].price))
    return scored


def _price_fit_score(price: float, prefs: UserPreferences) -> float:
    """Score how well product price fits user budget preferences."""
    has_min = prefs.min_price is not None
    has_max = prefs.max_price is not None
    if not has_min and not has_max:
        return 0.0

    min_price = prefs.min_price if has_min else None
    max_price = prefs.max_price if has_max else None

    if has_min and has_max and min_price is not None and max_price is not None:
        if min_price <= price <= max_price:
            return RANK_WEIGHTS["price_fit_strong"]
        width = max(max_price - min_price, 1.0)
        near_low = min_price - (0.2 * width)
        near_high = max_price + (0.2 * width)
        if near_low <= price <= near_high:
            return RANK_WEIGHTS["price_fit_near"]
        return RANK_WEIGHTS["price_fit_out_of_range"]

    if has_max and max_price is not None:
        if price <= max_price:
            return RANK_WEIGHTS["price_fit_strong"]
        if price <= max_price * 1.15:
            return RANK_WEIGHTS["price_fit_near"]
        return RANK_WEIGHTS["price_fit_out_of_range"]

    if has_min and min_price is not None:
        if price >= min_price:
            return RANK_WEIGHTS["price_fit_strong"]
        if price >= min_price * 0.85:
            return RANK_WEIGHTS["price_fit_near"]
        return RANK_WEIGHTS["price_fit_out_of_range"]

    return 0.0


def _product_to_card(p: Product, score: float | None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "id": p.id,
        "name": p.name,
        "price": p.price,
        "currency": p.currency,
        "category": p.category,
        "brand": p.brand,
    }
    if score is not None:
        card["relevance_score"] = round(score, 2)
    return card


def _format_reply(
    top: list[tuple[Product, float]],
    prefs: UserPreferences,
    plan: SearchPlan,
    *,
    relaxed: bool,
) -> str:
    lines: list[str] = []
    mq = plan.match_quality
    notes = plan.retrieval_notes

    if mq == "weak":
        lines.append(
            "I couldn't find a strong match for your full request in this catalog."
        )
        lines.append(
            "Here are the closest alternatives from the catalog (real items only)."
        )
        if notes:
            lines.append("Adjustments: " + " ".join(notes))
    elif plan.intent == "browse_or_explore":
        lines.append(
            "Here are some top picks from the sample catalog based on your message."
        )
    else:
        lines.append(
            "Here are the best matches from the sample catalog given your preferences."
        )

    if mq != "weak" and relaxed and notes:
        lines.append("Note: " + " ".join(notes))

    detail_bits = []
    if prefs.categories:
        detail_bits.append(f"categories: {', '.join(prefs.categories)}")
    if prefs.max_price is not None:
        detail_bits.append(f"budget up to ${prefs.max_price:g}")
    if prefs.brands:
        detail_bits.append(f"brands: {', '.join(prefs.brands)}")
    if detail_bits:
        lines.append("Filters considered: " + "; ".join(detail_bits) + ".")

    for i, (p, sc) in enumerate(top[:5], start=1):
        lines.append(
            f"{i}. {p.name} — ${p.price:g} {p.currency} "
            f"({p.category}, {p.brand}; score {sc:.1f})"
        )
    if relaxed and mq != "weak" and not notes:
        lines.append(
            "(Some constraints were relaxed so you still get useful recommendations.)"
        )
    return "\n".join(lines)


def run_deterministic_shopping(message: str) -> DeterministicTurnResult:
    """Run the full deterministic pipeline (safe fallback if catalog missing)."""
    text = (message or "").strip()
    if not text:
        return DeterministicTurnResult(
            reply="Please send a non-empty message so I can search the catalog.",
            mode="fallback",
            preferences={},
            search_plan={
                "intent": "none",
                "filters_applied": [],
                "sort": "n/a",
                "relaxed": False,
            },
            products=[],
        )

    try:
        catalog = load_product_catalog()
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as e:
        logger.warning("catalog load failed: %s", e)
        return DeterministicTurnResult(
            reply=(
                "The shopping catalog is temporarily unavailable. "
                "Please try again later."
            ),
            mode="fallback",
            preferences={},
            search_plan={
                "intent": "error",
                "filters_applied": [],
                "sort": "n/a",
                "relaxed": False,
            },
            products=[],
        )

    if not catalog:
        return DeterministicTurnResult(
            reply="The product catalog is empty; nothing to search yet.",
            mode="fallback",
            preferences={},
            search_plan={
                "intent": "error",
                "filters_applied": [],
                "sort": "n/a",
                "relaxed": False,
            },
            products=[],
        )

    candidates, prefs, relaxed, retrieval_notes = retrieve_candidates_with_relaxation(
        catalog, text
    )

    ranked = rank_products(candidates, text, prefs)
    top = ranked[:8]

    match_quality = assess_match_quality(top, prefs, retrieval_notes)
    plan = build_search_plan(
        text,
        prefs,
        relaxed=relaxed,
        match_quality=match_quality,
        retrieval_notes=retrieval_notes,
    )

    reply = _format_reply(top, prefs, plan, relaxed=relaxed)
    cards = [_product_to_card(p, sc) for p, sc in top[:5]]
    return DeterministicTurnResult(
        reply=reply,
        mode="deterministic",
        preferences=prefs.to_public_dict(),
        search_plan=plan.to_public_dict(),
        products=cards,
    )
