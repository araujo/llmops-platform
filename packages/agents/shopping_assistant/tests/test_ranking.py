"""Unit tests for deterministic ranking (tiered weights, name vs blob)."""

from __future__ import annotations

import pytest

from shopping_assistant.domain.models import Product, UserPreferences
from shopping_assistant.service.deterministic import rank_products

pytestmark = pytest.mark.realistic_eval


def _p(
    pid: str,
    *,
    name: str,
    category: str,
    price: float = 50.0,
    tags: tuple[str, ...] = (),
    colors: tuple[str, ...] = (),
) -> Product:
    return Product(
        id=pid,
        name=name,
        category=category,
        brand="Brand",
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
    """Sample catalog: single sneaker row should stay top after retrieval."""
    from shopping_assistant.service.deterministic import (
        extract_preferences,
        load_product_catalog,
        retrieve_candidates_with_relaxation,
    )

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
    from shopping_assistant.service.deterministic import (
        extract_preferences,
        load_product_catalog,
        retrieve_candidates_with_relaxation,
    )

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
    from shopping_assistant.service.deterministic import (
        extract_preferences,
        load_product_catalog,
        retrieve_candidates_with_relaxation,
    )

    msg = "Find a perfume gift under 80 dollars"
    catalog = load_product_catalog()
    prefs = extract_preferences(msg, catalog)
    cands, prefs2, _, _ = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    assert not cands
    assert rank_products(cands, msg, prefs2) == []
