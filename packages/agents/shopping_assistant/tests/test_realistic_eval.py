"""Realistic evaluation scenarios for the shopping assistant (agent-local).

Assertions focus on structure, grounded catalog IDs, and relevance signals—not
verbatim reply text. Run from repo root::

    python -m pytest packages/agents/shopping_assistant/tests -m realistic_eval -q

Or with coverage::

    python -m pytest packages/agents/shopping_assistant/tests \\
        --cov=shopping_assistant --cov-report=term-missing -q
"""

from __future__ import annotations

import pytest

from shopping_assistant.domain.models import preferences_from_public
from shopping_assistant.service.deterministic import (
    assess_match_quality,
    extract_preferences,
    load_product_catalog,
    rank_products,
    retrieve_candidates_with_relaxation,
    run_deterministic_shopping,
)

pytestmark = pytest.mark.realistic_eval


def _catalog_id_set() -> set[str]:
    return {p.id for p in load_product_catalog()}


def _assert_grounded_products(product_cards: list[dict], allowed: set[str]) -> None:
    assert product_cards, "expected at least one catalog-backed product row"
    for row in product_cards:
        assert row.get("id") in allowed, "product id must exist in loaded catalog"
        assert isinstance(row.get("name"), str) and row["name"].strip()


@pytest.mark.parametrize(
    ("message", "check_prefs"),
    [
        (
            "I need black sneakers under 100 dollars",
            lambda p: (
                p.max_price == 100.0
                and "black" in p.colors
                and "sneakers" in p.product_types
            ),
        ),
        (
            "Find a perfume gift under 80 dollars",
            lambda p: (
                p.max_price == 80.0
                and p.gift_intent is True
                and "perfume" in p.product_types
            ),
        ),
        (
            "Show me a work bag",
            lambda p: ("bag" in p.product_types and "work" in p.use_cases),
        ),
    ],
)
def test_extract_preferences_realistic_queries(
    message: str,
    check_prefs,
) -> None:
    catalog = load_product_catalog()
    prefs = extract_preferences(message, catalog)
    assert check_prefs(prefs), f"unexpected prefs: {prefs.to_public_dict()}"


def test_eval_black_sneakers_under_100_pipeline() -> None:
    """Sample catalog may lack footwear; expect grounded fallback, not invented SKUs."""
    msg = "I need black sneakers under 100 dollars"
    catalog = load_product_catalog()
    allowed = _catalog_id_set()

    prefs = extract_preferences(msg, catalog)
    assert prefs.max_price == 100.0
    assert "black" in prefs.colors
    assert "sneakers" in prefs.product_types

    cands, prefs2, _relaxed, _notes = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    assert cands, "candidates should be non-empty after retrieval"
    assert {p.id for p in cands}.issubset(allowed)

    ranked = rank_products(cands, msg, prefs2)
    assert ranked, "ranking should return at least one scored row"
    top_id, top_score = ranked[0][0].id, ranked[0][1]
    assert top_id in allowed
    assert isinstance(top_score, float)

    out = run_deterministic_shopping(msg)
    assert out.mode == "deterministic"
    _assert_grounded_products(out.products, allowed)
    plan = out.search_plan
    assert plan.get("intent") == "find_products"
    assert isinstance(plan.get("filters_applied"), list)
    assert plan.get("match_quality") in ("strong", "partial", "weak")
    prefs_roundtrip = preferences_from_public(out.preferences or {})
    expected_mq = assess_match_quality(
        ranked[:8],
        prefs_roundtrip,
        list(plan.get("retrieval_notes") or []),
    )
    assert plan.get("match_quality") == expected_mq


def test_eval_perfume_gift_under_80_fallback_quality() -> None:
    """Fragrance is absent from sample catalog; semantic gate avoids irrelevant rows."""
    msg = "Find a perfume gift under 80 dollars"
    allowed = _catalog_id_set()

    out = run_deterministic_shopping(msg)
    assert out.mode == "deterministic"
    assert out.search_plan.get("match_quality") == "weak"
    prefs_dict = out.preferences or {}
    assert prefs_dict.get("gift_intent") is True
    assert "perfume" in (prefs_dict.get("product_types") or [])
    # Final prefs may include widened budget after retrieval relaxation.
    assert prefs_dict.get("max_price") in (80.0, 96.0, 100.0)

    assert out.products == []
    assert (
        "catalog" in out.reply.lower()
        or "match" in out.reply.lower()
        or "confidence" in out.reply.lower()
    )
    assert isinstance(out.reply, str) and len(out.reply) > 40


def test_eval_work_bag_retrieval_and_ranking() -> None:
    """Work + bag should steer toward carry/office-adjacent categories when possible."""
    msg = "Show me a work bag"
    catalog = load_product_catalog()
    allowed = _catalog_id_set()

    prefs = extract_preferences(msg, catalog)
    assert "bag" in prefs.product_types
    assert "work" in prefs.use_cases
    # Default catalog maps bags to accessories when no dedicated bag category.
    assert prefs.categories, "expected inferred categories for bag intent"

    cands, prefs2, _relaxed, _notes = retrieve_candidates_with_relaxation(
        catalog, msg, prefs=prefs
    )
    assert {p.id for p in cands}.issubset(allowed)
    assert cands, "expected non-empty candidate set"

    ranked = rank_products(cands, msg, prefs2)
    top = ranked[0][0]
    blob = top.searchable_blob()
    # Relevance: top item should tie to office/carry/accessories signals or keywords.
    relevance_ok = (
        top.category in prefs2.categories
        or "bag" in blob
        or "office" in blob
        or "work" in blob
        or "travel" in blob
        or "keyboard" in blob
        or "briefcase" in blob
        or "tote" in blob
    )
    assert relevance_ok, f"top product blob lacked expected signals: {blob!r}"

    out = run_deterministic_shopping(msg)
    _assert_grounded_products(out.products, allowed)
    assert out.search_plan.get("intent") == "find_products"


def test_search_plan_structure_for_realistic_queries() -> None:
    """Search plan exposes intent, filters, and match metadata."""
    for msg in (
        "I need black sneakers under 100 dollars",
        "Find a perfume gift under 80 dollars",
        "Show me a work bag",
    ):
        out = run_deterministic_shopping(msg)
        sp = out.search_plan
        assert sp.get("sort")
        assert "relaxed" in sp
        assert sp.get("match_quality") in ("strong", "partial", "weak")
        assert isinstance(sp.get("retrieval_notes"), list)
        assert isinstance(sp.get("filters_applied"), list)
