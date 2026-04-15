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
        if has_structured_semantic_intent(prefs):
            retrieval_notes.append(
                "No catalog rows matched required category + semantic product intent."
            )
            candidates = []
        else:
            candidates = _lexical_refine_candidates(catalog, text, prefs)
            if candidates:
                retrieval_notes.append(
                    "No exact filter match; took the closest lexical matches from the catalog."
                )
            else:
                retrieval_notes.append(
                    "No catalog rows matched your message; no fallback catalog sweep."
                )
    return candidates, prefs, relaxed, retrieval_notes

logger = logging.getLogger(__name__)


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

# Extra stopwords removed from extracted keywords before retrieval/ranking.
_RETRIEVAL_STOPWORDS = frozenset(
    {
        "like",
        "want",
        "looking",
        "please",
        "some",
        "any",
        "get",
        "give",
        "help",
        "would",
        "could",
    }
)

# Canonical product_type / intent -> extra substring hints (merged with PRODUCT_TYPE_KEYWORDS).
SYNONYM_MAP: dict[str, tuple[str, ...]] = {
    "sneakers": (
        "sneaker",
        "trainer",
        "trainers",
        "shoes",
        "footwear",
        "athletic",
        "running",
        "gym",
    ),
    "perfume": (
        "fragrance",
        "cologne",
        "eau",
        "scent",
        "parfum",
    ),
    "bag": (
        "tote",
        "satchel",
        "briefcase",
        "backpack",
        "crossbody",
        "carry",
        "luggage",
    ),
    "headphones": ("headset", "over-ear", "over ear", "ear cup"),
    "earbuds": ("earbud", "in-ear", "in ear", "buds"),
    "laptop": ("notebook", "ultrabook", "macbook"),
}

# When infer_catalog_categories yields nothing, map common intents to default category slugs
# (intersected with the live catalog) so retrieval is never category-blind for these intents.
INTENT_CATEGORY_DEFAULT_TERMS: dict[str, tuple[str, ...]] = {
    "sneakers": ("shoes", "footwear", "sneakers", "athletic shoes"),
    "perfume": ("fragrance", "beauty", "perfume", "personal care"),
    "bag": ("bags", "handbags", "tote", "satchel", "briefcase", "accessories"),
    "headphones": ("headphones",),
    "earbuds": ("earbuds",),
    "laptop": ("laptops",),
}

# Extra tokens dropped from plan-facing keywords (retrieval keywords unchanged).
_PLAN_STOPWORDS = _KEYWORD_STOPWORDS | _RETRIEVAL_STOPWORDS | frozenset(
    {
        "dollars",
        "usd",
        "need",
        "find",
        "show",
        "looking",
        "want",
    }
)


def _normalize_category_slugs(categories: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for c in categories:
        s = c.strip().lower()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _price_preference_summary(prefs: UserPreferences) -> str:
    if prefs.min_price is not None and prefs.max_price is not None:
        return f"${prefs.min_price:g}–${prefs.max_price:g}"
    if prefs.max_price is not None:
        return f"up to ${prefs.max_price:g}"
    if prefs.min_price is not None:
        return f"from ${prefs.min_price:g}"
    return ""


def _strip_price_phrases_for_plan(text: str) -> str:
    """Remove budget/price phrases so plan keywords reflect remaining intent tokens."""
    s = text.lower().strip()
    s = re.sub(
        r"(?:between)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:and|to)\s*\$?\s*(\d+(?:\.\d+)?)",
        " ",
        s,
    )
    s = re.sub(
        r"\$?\s*(\d+(?:\.\d+)?)\s*[-–]\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|usd)?",
        " ",
        s,
    )
    s = re.sub(
        r"(?:under|below|less than|max(?:imum)?|at most)\s*\$?\s*(\d+(?:\.\d+)?)",
        " ",
        s,
    )
    s = re.sub(
        r"(?:over|above|at least|min(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)",
        " ",
        s,
    )
    s = re.sub(r"\b(?:cheap|budget|affordable|inexpensive)\b", " ", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\s*dollars?\b", " ", s)
    s = re.sub(r"\$\s*\d+(?:\.\d+)?\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _category_defaults_for_plan(
    prefs: UserPreferences,
    message_lower: str,
    catalog_categories: frozenset[str],
) -> list[str]:
    """Default category slugs from product types + message tokens, ∩ catalog."""
    out: list[str] = []
    seen: set[str] = set()
    for pt in prefs.product_types:
        for c in INTENT_CATEGORY_DEFAULT_TERMS.get(pt, ()):
            if c in catalog_categories and c not in seen:
                seen.add(c)
                out.append(c)
    for token, candidates in TOKEN_TO_CATEGORY_CANDIDATES.items():
        if not re.search(rf"\b{re.escape(token)}\b", message_lower):
            continue
        for c in _pick_present(candidates, catalog_categories):
            if c not in seen:
                seen.add(c)
                out.append(c)
    return out


def _semantic_hints_by_product_type(prefs: UserPreferences) -> dict[str, list[str]]:
    return {
        pt: list(semantic_hints_for_product_type(pt)) for pt in prefs.product_types
    }


def _plan_keyword_noise_tokens(prefs: UserPreferences) -> frozenset[str]:
    """Tokens that describe product type / synonyms, not free-text query facets."""
    noise: set[str] = set()
    for pt in prefs.product_types:
        for h in semantic_hints_for_product_type(pt):
            noise.add(h)
            for part in h.replace("-", " ").split():
                if len(part) >= 2:
                    noise.add(part)
    return frozenset(noise)


def _normalize_keywords_for_plan(message: str, prefs: UserPreferences) -> list[str]:
    stripped = _strip_price_phrases_for_plan(message)
    noise = _plan_keyword_noise_tokens(prefs)
    brand_lower = {b.strip().lower() for b in prefs.brands if b.strip()}
    out: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", stripped):
        t = token.lower().replace("_", "-")
        if len(t) < 3:
            continue
        if t in _PLAN_STOPWORDS or t in _COLOR_WORDS:
            continue
        if t in brand_lower or t in noise:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _plan_normalized_categories(
    prefs: UserPreferences,
    message_lower: str,
    catalog_categories: frozenset[str],
) -> tuple[list[str], list[str]]:
    """Return (normalized active categories, intent default candidates ∩ catalog).

    When ``prefs.categories`` is empty but product types (or message tokens)
    imply a known intent, fall back to catalog-backed default slugs so the plan
    is never category-blind for common intents.
    """
    normalized = _normalize_category_slugs(prefs.categories)
    defaults = _category_defaults_for_plan(prefs, message_lower, catalog_categories)
    if not normalized and defaults:
        normalized = list(defaults)
    return normalized, defaults


# Tunable deterministic ranking weights (explicit keys for tuning).
RANK_WEIGHTS: dict[str, float] = {
    # Message tokens (name match is more salient than body-only hits).
    "lexical_token_in_name": 2.4,
    "lexical_token_in_blob": 1.0,
    "keyword_in_name": 1.9,
    "keyword_in_blob": 0.85,
    # Category: first slug in prefs is treated as the primary inferred category.
    "category_primary": 6.5,
    "category_secondary": 3.2,
    "brand_match": 3.2,
    "color_match": 2.9,
    # Product type (retrieval already enforced semantic gate; rank by name vs body).
    "product_type_match_name": 5.0,
    "product_type_match_soft": 2.6,
    "use_case_in_name": 2.4,
    "use_case_in_blob": 1.5,
    "style_match_in_name": 1.1,
    "style_match_in_blob": 0.75,
    # Price fit (range / ceiling / floor).
    "price_fit_strong": 2.9,
    "price_fit_near": 1.0,
    "price_fit_out_of_range": -1.5,
    # Extra headroom under a max budget (capped; only when price <= max).
    "price_under_budget_bonus_cap": 1.6,
    "price_under_budget_bonus_scale": 2.2,
}

# Below this rank score, structured queries are treated as weak matches for messaging.
WEAK_MATCH_SCORE_THRESHOLD = 14.0


def _load_catalog_raw() -> list[dict[str, Any]]:
    pkg = resources.files("shopping_assistant.data.samples")
    raw = pkg.joinpath("products.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("catalog root must be a list")
    return data


def load_product_catalog() -> list[Product]:
    """Load products from ``data/samples/products.json``."""
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


def semantic_hints_for_product_type(pt: str) -> tuple[str, ...]:
    """Merge keyword + synonym hints for a canonical product type (deterministic)."""
    merged: list[str] = []
    seen: set[str] = set()
    for h in PRODUCT_TYPE_KEYWORDS.get(pt, ()) + SYNONYM_MAP.get(pt, ()):
        h2 = h.strip().lower()
        if not h2 or h2 in seen:
            continue
        seen.add(h2)
        merged.append(h2)
    return tuple(merged)


def _hint_matches_blob(hint: str, blob: str) -> bool:
    if len(hint) <= 3:
        return bool(re.search(rf"\b{re.escape(hint)}\b", blob))
    return hint in blob


def apply_intent_category_defaults(
    prefs: UserPreferences,
    catalog_categories: frozenset[str],
) -> None:
    """If categories are empty but intent is known, map to default catalog categories."""
    if prefs.categories:
        return
    if not prefs.product_types:
        return
    for pt in prefs.product_types:
        for c in INTENT_CATEGORY_DEFAULT_TERMS.get(pt, ()):
            if c in catalog_categories and c not in prefs.categories:
                prefs.categories.append(c)


def normalize_retrieval_keywords(prefs: UserPreferences) -> None:
    """Drop stopwords and normalize tokens used for lexical scoring."""
    stop = _KEYWORD_STOPWORDS | _RETRIEVAL_STOPWORDS
    out: list[str] = []
    seen: set[str] = set()
    for kw in prefs.keywords:
        k = kw.strip().lower().replace("_", "-")
        if len(k) < 3 or k in stop or k in seen:
            continue
        seen.add(k)
        out.append(k)
    prefs.keywords = out


def hard_semantic_match(p: Product, prefs: UserPreferences) -> bool:
    """Require blob match for declared product types (category already enforced)."""
    if not prefs.product_types:
        return True
    blob = p.searchable_blob()
    return any(
        any(_hint_matches_blob(h, blob) for h in semantic_hints_for_product_type(pt))
        for pt in prefs.product_types
    )


def has_structured_semantic_intent(prefs: UserPreferences) -> bool:
    return bool(prefs.product_types or prefs.categories)


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
    apply_intent_category_defaults(prefs, catalog_cats)
    normalize_retrieval_keywords(prefs)
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
        any(_hint_matches_blob(h, blob) for h in semantic_hints_for_product_type(pt))
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
    if any(
        x in " ".join(retrieval_notes).lower()
        for x in ("full catalog", "semantic product")
    ) and top_s < 11.0:
        return "weak"
    return "strong"


def build_search_plan(
    message: str,
    prefs: UserPreferences,
    *,
    relaxed: bool,
    match_quality: str = "strong",
    retrieval_notes: list[str] | None = None,
    catalog_categories: frozenset[str] | None = None,
) -> SearchPlan:
    cats = catalog_categories if catalog_categories is not None else frozenset()
    message_lower = message.strip().lower()
    normalized_categories, intent_category_defaults = _plan_normalized_categories(
        prefs, message_lower, cats
    )
    semantic_hints = _semantic_hints_by_product_type(prefs)
    normalized_keywords = _normalize_keywords_for_plan(message, prefs)
    query_after_price = _strip_price_phrases_for_plan(message)
    price_summary = _price_preference_summary(prefs)

    filters: list[str] = []
    if prefs.max_price is not None:
        filters.append(f"price <= {prefs.max_price:g}")
    if prefs.min_price is not None:
        filters.append(f"price >= {prefs.min_price:g}")
    if normalized_categories:
        filters.append(f"categories: {normalized_categories}")
    if prefs.product_types:
        filters.append(f"product_types: {list(prefs.product_types)}")
        filters.append("product_type_semantic_match: required")
    if prefs.brands:
        filters.append(f"brands: {list(prefs.brands)}")
    if prefs.colors:
        filters.append(f"facet_colors: {list(prefs.colors)}")
    if prefs.style_keywords:
        filters.append(f"facet_style_keywords: {list(prefs.style_keywords)}")
    if prefs.use_cases:
        filters.append(f"facet_use_cases: {list(prefs.use_cases)}")
    if prefs.gift_intent:
        filters.append("gift_intent: true")

    intent = "find_products"
    if not any(
        (
            normalized_categories,
            prefs.brands,
            prefs.product_types,
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
        product_types=list(prefs.product_types),
        semantic_hints_by_product_type=semantic_hints,
        intent_category_defaults=intent_category_defaults,
        normalized_categories=normalized_categories,
        normalized_keywords=normalized_keywords,
        facet_colors=list(prefs.colors),
        facet_style_keywords=list(prefs.style_keywords),
        facet_use_cases=list(prefs.use_cases),
        query_text_after_price_strip=query_after_price,
        price_preference_summary=price_summary,
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
    """Choose nearest catalog categories using product-type overlap + semantic gate.

    Only categories that contain at least one product passing :func:`hard_semantic_match`
    are considered, so unrelated departments (e.g. kitchen) are never mapped in.
    """
    if prefs.categories or not prefs.product_types:
        return []
    category_scores: dict[str, float] = {}
    for category in catalog_category_slugs(products):
        cat_products = [p for p in products if p.category == category]
        if not any(hard_semantic_match(p, prefs) for p in cat_products):
            continue
        score = 0.0
        cat_blob = " ".join([category] + [p.searchable_blob() for p in cat_products])
        for product_type in prefs.product_types:
            for hint in semantic_hints_for_product_type(product_type):
                if hint in cat_blob:
                    score += 1.0
        if score > 0:
            category_scores[category] = score
    return [
        c
        for c, _ in sorted(category_scores.items(), key=lambda x: (-x[1], x[0]))[:2]
    ]


def _product_category_allowed(p: Product, categories: list[str]) -> bool:
    """True if ``p`` is in one of the allowed category slugs (case-insensitive)."""
    if not categories:
        return True
    plc = p.category.strip().lower()
    allowed = {c.strip().lower() for c in categories if c.strip()}
    return plc in allowed


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
        for hint in semantic_hints_for_product_type(pt):
            if _hint_matches_blob(hint, blob):
                score += 1.8
    for use_case in prefs.use_cases:
        for hint in USE_CASE_KEYWORDS.get(use_case, ()):
            if hint in blob:
                score += 0.8
    if prefs.categories and _product_category_allowed(product, prefs.categories):
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
    """Keep products with positive lexical relevance only (no zero-score filler)."""
    if not products:
        return []
    scored = [(p, _lexical_retrieval_score(p, message, prefs)) for p in products]
    positives = [(p, sc) for p, sc in scored if sc > 0]
    if not positives:
        return []
    positives.sort(key=lambda x: (-x[1], x[0].price))
    keep = min(max(5, len(positives)), 20)
    return [p for p, _ in positives[:keep]]


def retrieve_candidates(
    products: list[Product],
    message: str,
    prefs: UserPreferences,
    *,
    strict_colors: bool,
) -> list[Product]:
    """Deterministic candidate retrieval: price/brand/color, category, semantic gate.

    When ``product_types`` is set, every candidate must match
    :func:`hard_semantic_match` (expanded hints per type). Those rows are passed
    through to ranking unchanged—no lexical top-K that could admit irrelevant
    items with score 0.
    """
    base = filter_products(products, prefs, strict_colors=strict_colors)
    if not base:
        return []
    if prefs.product_types:
        hardened = [p for p in base if hard_semantic_match(p, prefs)]
        return hardened
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
        if prefs.categories and not _product_category_allowed(p, prefs.categories):
            continue
        if prefs.brands:
            if p.brand not in prefs.brands:
                continue
        if strict_colors and prefs.colors and not _matches_color(p, prefs.colors):
            continue
        out.append(p)
    return out


def _normalized_category_order(prefs: UserPreferences) -> list[str]:
    return [c.strip().lower() for c in prefs.categories if c.strip()]


def _category_rank_score(p: Product, prefs: UserPreferences) -> float:
    """Higher score when the product sits in the primary (first) inferred category."""
    if not prefs.categories:
        return 0.0
    order = _normalized_category_order(prefs)
    plc = p.category.strip().lower()
    if plc not in order:
        return 0.0
    if order and plc == order[0]:
        return RANK_WEIGHTS["category_primary"]
    return RANK_WEIGHTS["category_secondary"]


def _product_type_rank_contribution(p: Product, pt: str) -> float:
    """Name hits beat tag-only hits for clearer ordering among valid candidates."""
    name_lower = p.name.lower()
    hints = semantic_hints_for_product_type(pt)
    blob = p.searchable_blob()
    if any(_hint_matches_blob(h, name_lower) for h in hints):
        return RANK_WEIGHTS["product_type_match_name"]
    if any(_hint_matches_blob(h, blob) for h in hints):
        return RANK_WEIGHTS["product_type_match_soft"]
    return 0.0


def _price_under_budget_bonus(price: float, prefs: UserPreferences) -> float:
    """Small bonus for staying under budget (more headroom → slightly higher score)."""
    if prefs.max_price is None or price > prefs.max_price + 0.005:
        return 0.0
    cap = RANK_WEIGHTS["price_under_budget_bonus_cap"]
    scale = RANK_WEIGHTS["price_under_budget_bonus_scale"]
    headroom = (prefs.max_price - price) / max(prefs.max_price, 1.0)
    return min(cap, headroom * scale)


def rank_products(
    candidates: list[Product],
    message: str,
    prefs: UserPreferences,
) -> list[tuple[Product, float]]:
    """Return (product, score) sorted by score descending.

    Operates only on the candidate list produced by retrieval (semantic + category
    gates). Scoring is explicit and driven by :data:`RANK_WEIGHTS`:

    - Lexical: message tokens and extracted keywords, weighted higher when they
      appear in the product title vs the full searchable blob.
    - Category: primary inferred category (first in ``prefs.categories``) beats
      other allowed categories.
    - Product type: title match vs tag-only match (both already semantically valid).
    - Color, brand, use case, style: name-first where applicable.
    - Price: range fit plus a capped bonus for comfortable headroom under ``max_price``.
    """
    lower = message.lower()
    msg_tokens = {t for t in re.findall(r"[a-z0-9]+", lower) if len(t) >= 3}
    scored: list[tuple[Product, float]] = []
    for p in candidates:
        blob = p.searchable_blob()
        name_lower = p.name.lower()
        s = 0.0
        for w in msg_tokens:
            if w in name_lower:
                s += RANK_WEIGHTS["lexical_token_in_name"]
            elif w in blob:
                s += RANK_WEIGHTS["lexical_token_in_blob"]
        for kw in prefs.keywords:
            if kw in name_lower:
                s += RANK_WEIGHTS["keyword_in_name"]
            elif kw in blob:
                s += RANK_WEIGHTS["keyword_in_blob"]

        s += _category_rank_score(p, prefs)

        for b in prefs.brands:
            if b.lower() in p.brand.lower():
                s += RANK_WEIGHTS["brand_match"]
        if prefs.colors and _matches_color(p, prefs.colors):
            s += RANK_WEIGHTS["color_match"]

        for pt in prefs.product_types:
            s += _product_type_rank_contribution(p, pt)

        for use_case in prefs.use_cases:
            hints = USE_CASE_KEYWORDS.get(use_case, ())
            if any(hint in name_lower for hint in hints):
                s += RANK_WEIGHTS["use_case_in_name"]
            elif any(hint in blob for hint in hints):
                s += RANK_WEIGHTS["use_case_in_blob"]

        for style in prefs.style_keywords:
            hints = STYLE_KEYWORDS.get(style, ())
            if any(hint in name_lower for hint in hints):
                s += RANK_WEIGHTS["style_match_in_name"]
            elif any(hint in blob for hint in hints):
                s += RANK_WEIGHTS["style_match_in_blob"]

        s += _price_fit_score(p.price, prefs)
        s += _price_under_budget_bonus(p.price, prefs)
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

    if not top:
        lines.append(
            "No products in this catalog matched your filters and semantic product intent."
        )
        if notes:
            lines.append("Details: " + " ".join(notes))
        detail_bits = []
        if prefs.categories:
            detail_bits.append(f"categories: {', '.join(prefs.categories)}")
        if prefs.max_price is not None:
            detail_bits.append(f"budget up to ${prefs.max_price:g}")
        if prefs.brands:
            detail_bits.append(f"brands: {', '.join(prefs.brands)}")
        if detail_bits:
            lines.append("Filters considered: " + "; ".join(detail_bits) + ".")
        return "\n".join(lines)

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
        catalog_categories=catalog_category_slugs(catalog),
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
