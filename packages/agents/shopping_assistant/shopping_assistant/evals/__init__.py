"""Eval assets and runners (datasets under ``evals/datasets/``).

Heavy imports (graph stack) load only when ``list_local_datasets`` /
``run_eval_suite`` are used, so unit tests can import ``evals.scoring`` alone.
"""

from __future__ import annotations

from shopping_assistant.paths import evals_datasets_dir, evals_dir

__all__ = [
    "evals_datasets_dir",
    "evals_dir",
    "list_local_datasets",
    "run_eval_suite",
]


def __getattr__(name: str):
    if name == "list_local_datasets":
        from shopping_assistant.evals.runner import list_local_datasets as _f

        return _f
    if name == "run_eval_suite":
        from shopping_assistant.evals.runner import run_eval_suite as _r

        return _r
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
