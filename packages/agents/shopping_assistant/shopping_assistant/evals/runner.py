"""Offline eval harness: JSON datasets under ``evals/datasets/``."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from shopping_assistant.domain.state import ShoppingGraphState
from shopping_assistant.evals.scoring import evaluate_expectation
from shopping_assistant.orchestration.graph import run_shopping_turn
from shopping_assistant.paths import evals_datasets_dir

logger = logging.getLogger(__name__)


def list_local_datasets() -> list[Path]:
    """List files in ``evals/datasets`` (non-recursive)."""
    root = evals_datasets_dir()
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_file())


def _load_dataset(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("dataset root must be a JSON object")
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError('dataset must contain a "cases" array')
    return data


def run_eval_suite(dataset_stem: str) -> dict[str, Any]:
    """Run JSON cases from ``evals/datasets/{stem}.json``.

    Dataset format::

        {
          "description": "optional",
          "cases": [
            {
              "id": "optional-case-id",
              "query": "user message",
              "expect": {
                "mode": "deterministic",
                "expected_product_id": "trail-runner-sneaker-blk",
                "expected_no_match": false,
                "expected_match_quality": "strong",
                "expected_brand": "Nike",
                "expected_category": "shoes",
                "expected_product_type": "sneakers"
              }
            }
          ]
        }
    """

    root = evals_datasets_dir()
    path = root / f"{dataset_stem}.json"
    if not path.is_file():
        return {
            "ok": False,
            "error": f"dataset not found: {path}",
            "dataset_stem": dataset_stem,
        }

    try:
        spec = _load_dataset(path)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        logger.warning("eval dataset load failed: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "dataset_stem": dataset_stem,
        }

    cases_in = spec.get("cases")
    assert isinstance(cases_in, list)
    case_rows: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    for i, raw in enumerate(cases_in):
        if not isinstance(raw, dict):
            failed += 1
            case_rows.append(
                {
                    "index": i,
                    "ok": False,
                    "detail": "case must be an object",
                },
            )
            continue

        case_id = str(raw.get("id") or f"case_{i}")
        query = raw.get("query")
        if not isinstance(query, str):
            failed += 1
            case_rows.append(
                {
                    "id": case_id,
                    "ok": False,
                    "detail": 'each case needs a string "query"',
                },
            )
            continue

        expect = raw.get("expect")
        if expect is not None and not isinstance(expect, dict):
            failed += 1
            case_rows.append(
                {
                    "id": case_id,
                    "ok": False,
                    "detail": '"expect" must be an object when present',
                },
            )
            continue

        try:
            result: ShoppingGraphState = run_shopping_turn(query.strip())
        except Exception as e:
            failed += 1
            case_rows.append(
                {
                    "id": case_id,
                    "ok": False,
                    "detail": f"graph error: {e}",
                },
            )
            continue

        mode = str(result.get("mode") or "")
        products = result.get("products") or []
        if not isinstance(products, list):
            products = []
        product_ids = [
            str(row.get("id"))
            for row in products
            if isinstance(row, dict) and row.get("id") is not None
        ]
        search_plan = result.get("search_plan") or {}
        if not isinstance(search_plan, dict):
            search_plan = {}
        match_quality = str(search_plan.get("match_quality") or "")

        exp = expect or {}
        ok, detail = evaluate_expectation(result, exp)
        if ok:
            passed += 1
        else:
            failed += 1

        case_rows.append(
            {
                "id": case_id,
                "ok": ok,
                "detail": detail,
                "mode": mode,
                "products": product_ids,
                "search_plan": search_plan,
                "match_quality": match_quality,
            },
        )

    summary = {
        "ok": failed == 0,
        "dataset_stem": dataset_stem,
        "dataset_path": str(path),
        "description": spec.get("description", ""),
        "passed": passed,
        "failed": failed,
        "total": len(case_rows),
        "cases": case_rows,
    }
    return summary
