"""Eval assets and runners (datasets under ``evals/datasets/``)."""

from shopping_assistant.evals.runner import list_local_datasets, run_eval_suite
from shopping_assistant.paths import evals_datasets_dir, evals_dir

__all__ = [
    "evals_datasets_dir",
    "evals_dir",
    "list_local_datasets",
    "run_eval_suite",
]
