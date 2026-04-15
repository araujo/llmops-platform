"""Unit tests for deterministic ranking (tiered weights, name vs blob)."""

from __future__ import annotations

import pytest

from shopping_assistant.domain.models import Product, UserPreferences
from shopping_assistant.service.deterministic import (
    assess_match_quality,
    extract_brands_from_message,
    extract_preferences,
    load_product_catalog,
    rank_products,
    retrieve_candidates_with_relaxation,
)

pytestmark = pytest.mark.realistic_eval


def _p(
    pid: str,
    *,
    name: str,
    category: str,
    brand: str = "Brand",
    price: float = 50.0,
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


def test_ranking_prefers_primary_category_over_secondary() -> None:
    """First slug in prefs.categories should rank above other allowed slugs."""
    prefs = UserPreferences(
        categories=["shoes", "accessories"],
        product_types=[],
    )
    secondary = _p("a", name="Accessory Thing", category="accessories")
    primary = _p("b", name="Shoe Thing", category="shoes")
    ranked = rank_products([secondary, primary], "hi", prefs)
    assert ranked[0][0].id == "b"
    assert ranked[0][1] > ranked[1][1]


def test_ranking_prefers_product_type_hint_in_title() -> None:
    """Title hint should outrank tag-only hints among valid rows."""
    prefs = UserPreferences(
        categories=["shoes"],
        product_types=["sneakers"],
    )
    tag_only = _p(
        "t1",
        name="Plain Athletic",
        category="shoes",
        tags=("sneakers", "running"),
        colors=("white",),
    )
    name_hit = _p(
        "t2",
        name="Trail Runner Sneakers",
        category="shoes",
        tags=("athletic",),
        colors=("black",),
    )
    ranked = rank_products([tag_only, name_hit], "sneakers", prefs)
    assert ranked[0][0].id == "t2"
    assert ranked[0][1] >= ranked[1][1]


def test_ranking_black_sneakers_trail_runner_on_top() -> None:
    """Max price excludes pricier Nike shoe; top under-budget sneaker wins."""
    msg = "I need black sneakers under 100 dollars"
    catalog = load_product_catalog()
    prefs = extract_preferences(msg, catalog)
    cands, prefs2, _, _ = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    assert cands
    ranked = rank_products(cands, msg, prefs2)
    assert ranked[0][0].id == "trail-runner-sneaker-blk"


def test_ranking_work_bag_leather_tote_on_top() -> None:
    """Sample catalog: work + bag intent should rank the work tote first."""
    msg = "Show me a work bag"
    catalog = load_product_catalog()
    prefs = extract_preferences(msg, catalog)
    cands, prefs2, _, _ = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    assert cands
    ranked = rank_products(cands, msg, prefs2)
    assert ranked[0][0].id == "leather-work-tote-sm"


def test_ranking_perfume_no_candidates_empty_ranked() -> None:
    """No semantic matches → empty candidates → empty ranking."""
    msg = "Find a perfume gift under 80 dollars"
    catalog = load_product_catalog()
    prefs = extract_preferences(msg, catalog)
    cands, prefs2, _, _ = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    assert not cands
    assert rank_products(cands, msg, prefs2) == []


def test_extract_brand_nike_from_message() -> None:
    assert "Nike" in extract_brands_from_message(
        "show me nike shoes",
        load_product_catalog(),
    )


def test_nike_shoes_retrieval_respects_brand() -> None:
    """Requested brand filters to that manufacturer's rows (sample JSON includes Nike)."""
    msg = "Show me Nike shoes"
    catalog = load_product_catalog()
    prefs = extract_preferences(msg, catalog)
    assert "Nike" in prefs.brands
    cands, prefs2, _, _ = retrieve_candidates_with_relaxation(catalog, msg, prefs=prefs)
    assert len(cands) == 1
    assert cands[0].id == "nike-air-zoom-runner"
    assert prefs2.brand_relaxed is False


def test_assess_match_quality_tiers() -> None:
    """Strong vs partial vs weak from the same ranked row shape."""
    p = _p(
        "z",
        name="Nike Shoe",
        category="shoes",
        brand="Nike",
        tags=("sneakers",),
        colors=("black",),
    )
    weak_prefs = UserPreferences(product_types=["sneakers"], brands=[], categories=["shoes"])
    assert assess_match_quality([], weak_prefs, []) == "weak"

    partial_prefs = UserPreferences(
        product_types=["sneakers"],
        brands=["Nike"],
        categories=["shoes"],
        brand_relaxed=True,
    )
    assert assess_match_quality([(p, 99.0)], partial_prefs, []) == "partial"

    strong_prefs = UserPreferences(
        product_types=["sneakers"],
        brands=["Nike"],
        categories=["shoes"],
        brand_relaxed=False,
    )
    assert assess_match_quality([(p, 99.0)], strong_prefs, []) == "strong"


def test_ranking_exact_brand_beats_partial_when_both_in_pool() -> None:
    """Exact ``Product.brand`` match should score higher than substring-only."""
    prefs = UserPreferences(brands=["Acme"], product_types=[], categories=[])
    exact = _p("e", name="Widget", category="x", brand="Acme")
    partial = _p("p", name="Widget", category="x", brand="Acme Carrying Co.")
    ranked = rank_products([partial, exact], "acme", prefs)
    assert ranked[0][0].id == "e"
