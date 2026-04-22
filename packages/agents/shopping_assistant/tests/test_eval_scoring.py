"""Unit tests for shopping eval expectations (no LLM provider imports)."""

from __future__ import annotations

from shopping_assistant.domain.state import ShoppingGraphState
from shopping_assistant.evals.scoring import evaluate_expectation


def test_evaluate_expectation_mode() -> None:
    state: ShoppingGraphState = {
        "mode": "fallback",
        "assistant_message": "Hello",
        "products": [],
    }
    ok, detail = evaluate_expectation(state, {"mode": "fallback"})
    assert ok and detail == "ok"

    ok2, detail2 = evaluate_expectation(state, {"mode": "deterministic"})
    assert not ok2
    assert "deterministic" in detail2


def test_evaluate_expectation_min_products() -> None:
    state: ShoppingGraphState = {
        "mode": "deterministic",
        "assistant_message": "x",
        "products": [{"id": "a"}],
    }
    assert evaluate_expectation(state, {"min_products": 1})[0]
    assert not evaluate_expectation(state, {"min_products": 2})[0]


def test_evaluate_expectation_product_and_no_match_checks() -> None:
    state: ShoppingGraphState = {
        "mode": "deterministic",
        "assistant_message": "Found one",
        "products": [{"id": "nike-air-zoom-runner", "brand": "Nike"}],
    }
    assert evaluate_expectation(
        state,
        {"expected_product_id": "nike-air-zoom-runner"},
    )[0]
    assert evaluate_expectation(state, {"expected_no_match": False})[0]
    assert not evaluate_expectation(state, {"expected_no_match": True})[0]


def test_evaluate_expectation_signal_checks() -> None:
    state: ShoppingGraphState = {
        "mode": "deterministic",
        "assistant_message": "x",
        "products": [{"id": "1", "brand": "Nike", "category": "shoes"}],
        "preferences": {"brands": ["Nike"], "product_types": ["sneakers"]},
        "search_plan": {
            "match_quality": "strong",
            "normalized_categories": ["shoes"],
        },
    }
    assert evaluate_expectation(state, {"expected_brand": "Nike"})[0]
    assert evaluate_expectation(state, {"expected_category": "shoes"})[0]
    assert evaluate_expectation(
        state,
        {"expected_product_type": "sneakers"},
    )[0]
    assert evaluate_expectation(state, {"expected_match_quality": "strong"})[0]
