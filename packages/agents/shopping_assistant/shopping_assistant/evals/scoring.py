"""Shopping eval expectations and scoring (package-local only)."""

from __future__ import annotations

from typing import Any

from shopping_assistant.domain.state import ShoppingGraphState


def evaluate_expectation(
    result: ShoppingGraphState,
    expect: dict[str, Any],
) -> tuple[bool, str]:
    """Return ``(passed, detail)`` against a case ``expect`` block."""

    mode = str(result.get("mode") or "")
    products = result.get("products") or []
    n = len(products) if isinstance(products, list) else 0
    msg = str(result.get("assistant_message") or "")
    search_plan = result.get("search_plan") or {}
    if not isinstance(search_plan, dict):
        search_plan = {}
    preferences = result.get("preferences") or {}
    if not isinstance(preferences, dict):
        preferences = {}

    product_ids = {
        str(row.get("id"))
        for row in products
        if isinstance(row, dict) and row.get("id") is not None
    }

    if "mode" in expect:
        want = str(expect["mode"])
        if mode != want:
            return False, f"mode want {want!r} got {mode!r}"

    if "mode_in" in expect:
        allowed = list(expect["mode_in"])
        str_allowed = [str(x) for x in allowed]
        if mode not in str_allowed:
            return False, f"mode want one of {str_allowed} got {mode!r}"

    if "min_products" in expect:
        need = int(expect["min_products"])
        if n < need:
            return False, f"products count want >= {need} got {n}"

    if "max_products" in expect:
        cap = int(expect["max_products"])
        if n > cap:
            return False, f"products count want <= {cap} got {n}"

    if "assistant_substring" in expect:
        sub = str(expect["assistant_substring"])
        if sub.lower() not in msg.lower():
            return False, f"assistant_message missing substring {sub!r}"

    if expect.get("assistant_nonempty"):
        if not msg.strip():
            return False, "assistant_message empty"

    if "expected_product_id" in expect:
        want_id = str(expect["expected_product_id"])
        if want_id not in product_ids:
            got = sorted(product_ids)
            return False, f"expected product id {want_id!r} not in {got!r}"

    if "expected_product_ids_any" in expect:
        raw_any_ids = expect.get("expected_product_ids_any") or []
        any_ids = [str(v) for v in raw_any_ids]
        if any_ids and not any(pid in product_ids for pid in any_ids):
            got = sorted(product_ids)
            return False, f"expected one of product ids {any_ids!r}, got {got!r}"

    if "expected_no_match" in expect:
        want_no_match = bool(expect["expected_no_match"])
        got_no_match = n == 0
        if got_no_match != want_no_match:
            return (
                False,
                f"expected_no_match={want_no_match} got {got_no_match} "
                f"(products={n})",
            )

    if "expected_match_quality" in expect:
        want_quality = str(expect["expected_match_quality"])
        got_quality = str(search_plan.get("match_quality") or "")
        if got_quality != want_quality:
            return False, f"match_quality want {want_quality!r} got {got_quality!r}"

    if "expected_brand" in expect:
        want_brand = str(expect["expected_brand"]).strip().lower()
        pref_brands = [
            str(v).strip().lower() for v in (preferences.get("brands") or [])
        ]
        product_brands = [
            str(row.get("brand", "")).strip().lower()
            for row in products
            if isinstance(row, dict)
        ]
        if (
            want_brand
            and want_brand not in pref_brands
            and want_brand not in product_brands
        ):
            return False, f"brand signal {want_brand!r} missing in preferences/products"

    if "expected_category" in expect:
        want_cat = str(expect["expected_category"]).strip().lower()
        pref_cats = [
            str(v).strip().lower() for v in (preferences.get("categories") or [])
        ]
        plan_cats = [
            str(v).strip().lower()
            for v in (search_plan.get("normalized_categories") or [])
        ]
        product_cats = [
            str(row.get("category", "")).strip().lower()
            for row in products
            if isinstance(row, dict)
        ]
        if (
            want_cat
            and want_cat not in pref_cats
            and want_cat not in plan_cats
            and want_cat not in product_cats
        ):
            return (
                False,
                f"category signal {want_cat!r} missing in preferences/plan/products",
            )

    if "expected_product_type" in expect:
        want_type = str(expect["expected_product_type"]).strip().lower()
        pref_types = [
            str(v).strip().lower()
            for v in (preferences.get("product_types") or [])
        ]
        plan_types = [str(v).strip().lower() for v in (search_plan.get("product_types") or [])]
        if want_type and want_type not in pref_types and want_type not in plan_types:
            return (
                False,
                f"product_type signal {want_type!r} missing in preferences/plan",
            )

    return True, "ok"
