"""Shopping-local eval facade (datasets and scoring stay in ``evals/``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ShoppingEvalRunner:
    """Thin handle for offline eval entry points; no host or business logic."""

    def list_datasets(self) -> list[Path]:
        from shopping_assistant.evals.runner import list_local_datasets

        return list_local_datasets()

    def run_suite(self, dataset_stem: str) -> Any:
        from shopping_assistant.evals.runner import run_eval_suite

        return run_eval_suite(dataset_stem)
