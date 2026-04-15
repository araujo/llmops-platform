"""Unit tests for deterministic shopping (catalog, prefs, ranking)."""

from __future__ import annotations

import pytest

from shopping_assistant.domain.models import Product, UserPreferences
from shopping_assistant.service.deterministic import (
    assess_match_quality,
    catalog_category_slugs,
    extract_preferences,
    filter_products,
    infer_catalog_categories,
    infer_nearest_categories_from_types,
    load_product_catalog,
    rank_products,
    retrieve_candidates_with_relaxation,
    run_deterministic_shopping,
)


def _product(
    pid: str,
    name: str,
    category: str,
    *,
    price: float = 50.0,
    brand: str = "TestBrand",
    tags: tuple[str, ...] = (),
    colors: tuple[str, ...] = (),
) -> Product:
    return Product(
        id=pid,
        name=name,
        category=category,
        brand=brand,
        price=price,
        currency="USD",
        tags=tags,
        colors=colors,
    )


def test_load_catalog_non_empty() -> None:
    cat = load_product_catalog()
    assert len(cat) >= 10
    assert all(p.id and p.name for p in cat)


def test_extract_preferences_budget_and_category() -> None:
    cat = load_product_catalog()
    prefs = extract_preferences("Noise cancelling headphones under $350", cat)
    assert "headphones" in prefs.categories
    assert prefs.max_price == 350.0


def test_extract_preferences_range_gift_use_case_and_type() -> None:
    cat = load_product_catalog()
    prefs = extract_preferences(
        "Need a black work bag gift between 50 and 100 dollars",
        cat,
    )
    assert prefs.min_price == 50.0
    assert prefs.max_price == 100.0
    assert "black" in prefs.colors
    assert prefs.gift_intent is True
    assert "work" in prefs.use_cases
    assert "bag" in prefs.product_types
    # Sample catalog has no "bags" category; "bag" maps to "accessories".
    assert "accessories" in prefs.categories


def test_extract_preferences_type_for_realistic_queries() -> None:
    cat = load_product_catalog()
    p1 = extract_preferences("I need black sneakers under 100 dollars", cat)
    assert "sneakers" in p1.product_types
    assert p1.max_price == 100.0
    assert "black" in p1.colors

    p2 = extract_preferences("Find a perfume gift under 80 dollars", cat)
    assert "perfume" in p2.product_types
    assert p2.gift_intent is True
    assert p2.max_price == 80.0


def test_run_deterministic_shopping_returns_products() -> None:
    out = run_deterministic_shopping("Sony headphones under $400")
    assert out.mode == "deterministic"
    assert out.products
    assert any("Sony" in p["name"] or p.get("brand") == "Sony" for p in out.products)
    assert out.search_plan.get("intent")
    assert isinstance(out.preferences, dict)


def test_run_impossible_budget_semantic_gate_no_irrelevant_fillers() -> None:
    """Structured laptop intent with impossible price yields no filler SKUs."""
    out = run_deterministic_shopping("laptop under $5")
    assert out.mode == "deterministic"
    assert out.search_plan.get("match_quality") == "weak"
    assert out.products == []
    notes = out.search_plan.get("retrieval_notes") or []
    assert notes
    assert "semantic" in " ".join(notes).lower()


@pytest.mark.parametrize(
    "msg",
    [
        "",
        "   ",
    ],
)
def test_empty_message_fallback(msg: str) -> None:
    out = run_deterministic_shopping(msg)
    assert out.mode == "fallback"
    assert out.products == []


def test_infer_categories_sneakers_maps_to_shoes_when_present() -> None:
    catalog = [
        _product(
            "s1",
            "Runner Pro",
            "shoes",
            tags=("sneakers", "running"),
            colors=("black",),
        ),
        _product("h1", "Studio", "headphones"),
    ]
    prefs = extract_preferences("black sneakers under 90", catalog)
    assert "sneakers" in prefs.product_types
    assert "shoes" in prefs.categories
    filtered = filter_products(catalog, prefs, strict_colors=True)
    assert len(filtered) == 1
    assert filtered[0].category == "shoes"


def test_infer_categories_perfume_maps_to_fragrance_or_beauty() -> None:
    catalog = [
        _product("f1", "Eau Test", "fragrance", price=60.0),
        _product("k1", "Blender", "kitchen"),
    ]
    prefs = extract_preferences("perfume gift under 80 dollars", catalog)
    assert "perfume" in prefs.product_types
    assert prefs.gift_intent is True
    assert "fragrance" in prefs.categories
    filtered = filter_products(catalog, prefs, strict_colors=True)
    assert len(filtered) == 1 and filtered[0].id == "f1"


def test_infer_categories_work_bag_prefers_bags_then_accessories() -> None:
    """When both exist, phrase order picks bags-style categories first."""
    catalog = [
        _product("b1", "Leather Tote", "tote", price=120.0),
        _product("a1", "USB Hub", "accessories", price=40.0),
    ]
    prefs = extract_preferences("I need a work bag under 150", catalog)
    assert "bag" in prefs.product_types
    assert "work" in prefs.use_cases
    assert prefs.categories[0] == "tote"
    assert "accessories" in prefs.categories


def test_infer_catalog_categories_keyword_only_adds_if_in_catalog() -> None:
    """CATEGORY_KEYWORDS slugs are ignored when absent from the live catalog."""
    catalog = [_product("x", "Thing", "gadgets")]
    lower = "noise cancelling headphones"
    inferred = infer_catalog_categories(
        lower,
        UserPreferences(),
        catalog_category_slugs(catalog),
    )
    assert inferred == []


def test_retrieve_candidates_uses_lexical_matching_for_relevance() -> None:
    """Retrieval should trim to lexically relevant candidates before ranking."""
    catalog = [
        _product(
            "p1",
            "Acme Sport Sneakers",
            "shoes",
            price=89.0,
            tags=("running", "athletic"),
            colors=("black",),
        ),
        _product(
            "p2",
            "City Office Tote",
            "tote",
            price=120.0,
            tags=("work", "bag"),
            colors=("black",),
        ),
        _product(
            "p3",
            "Noise Cancel Headphones",
            "headphones",
            price=99.0,
            tags=("wireless",),
            colors=("white",),
        ),
    ]
    candidates, prefs, relaxed, _notes = retrieve_candidates_with_relaxation(
        catalog,
        "black sneakers under 100",
    )
    assert relaxed is False
    assert "sneakers" in prefs.product_types
    assert [p.id for p in candidates] == ["p1"]


def test_infer_nearest_categories_from_types_finds_best_match() -> None:
    catalog = [
        _product("p1", "Trail Runners", "footwear", tags=("running shoes", "sport")),
        _product("p2", "Office Keyboard", "accessories", tags=("office",)),
    ]
    prefs = UserPreferences(product_types=["sneakers"])
    nearest = infer_nearest_categories_from_types(catalog, prefs)
    assert nearest == ["footwear"]


def test_rank_prefers_category_color_price_fit_for_sneaker_query() -> None:
    catalog = [
        _product(
            "s1",
            "Runner Flex Sneakers",
            "shoes",
            price=95.0,
            tags=("running", "athletic"),
            colors=("black",),
        ),
        _product(
            "s2",
            "Trail Sneakers Pro",
            "shoes",
            price=130.0,
            tags=("running",),
            colors=("black",),
        ),
        _product(
            "h1",
            "Studio Headphones",
            "headphones",
            price=90.0,
            tags=("audio",),
            colors=("black",),
        ),
    ]
    prefs = extract_preferences("black sneakers under 100 dollars", catalog)
    ranked = rank_products(catalog, "black sneakers under 100 dollars", prefs)
    assert [p.id for p, _ in ranked][:2] == ["s1", "s2"]


def test_rank_prefers_brand_and_work_bag_signals() -> None:
    catalog = [
        _product(
            "b1",
            "Acme Office Tote",
            "tote",
            brand="Acme",
            price=110.0,
            tags=("work", "bag", "professional"),
            colors=("black",),
        ),
        _product(
            "b2",
            "Other Casual Tote",
            "tote",
            brand="Other",
            price=100.0,
            tags=("bag", "casual"),
            colors=("black",),
        ),
        _product(
            "a1",
            "Acme Keyboard",
            "accessories",
            brand="Acme",
            price=95.0,
            tags=("office", "keyboard"),
            colors=("black",),
        ),
    ]
    prefs = extract_preferences("Acme work bag under 120", catalog)
    ranked = rank_products(catalog, "Acme work bag under 120", prefs)
    assert ranked[0][0].id == "b1"


def test_weak_match_marks_low_score_structured_query() -> None:
    cat = load_product_catalog()
    prefs = extract_preferences("perfume gift under 80 dollars", cat)
    ranked = rank_products(cat, "perfume gift under 80 dollars", prefs)
    mq = assess_match_quality(ranked[:8], prefs, ["No exact filter match; ranked the full catalog for the closest items."])
    assert mq == "weak"


def test_run_deterministic_shopping_weak_reply_explains_and_lists_catalog_items() -> (
    None
):
    out = run_deterministic_shopping("perfume gift under 80 dollars")
    assert out.mode == "deterministic"
    assert out.search_plan.get("match_quality") == "weak"
    assert "semantic product intent" in out.reply.lower()
    assert all("id" in p and "name" in p for p in out.products)
    assert len(out.products) <= 5


def test_run_deterministic_shopping_strong_match_for_clear_product_query() -> None:
    out = run_deterministic_shopping("Sony WH-1000XM5 headphones under 400")
    assert out.search_plan.get("match_quality") == "strong"
    assert "couldn't find a strong match" not in out.reply.lower()
    assert any("Sony" in p.get("name", "") for p in out.products)
