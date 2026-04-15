"""Offline eval harness scaffolding (datasets live under ``evals/datasets/``)."""

from __future__ import annotations

from pathlib import Path

from shopping_assistant.paths import evals_datasets_dir


def list_local_datasets() -> list[Path]:
    """Return files under the package ``evals/datasets`` directory (non-recursive)."""
    root = evals_datasets_dir()
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_file())


def run_eval_suite(dataset_stem: str) -> None:
    """Placeholder entry point for a named dataset (e.g. ``gold_queries`` file stem)."""
    raise NotImplementedError(
        "Wire shopping_assistant.evals.runner to your harness; "
        f"datasets dir: {evals_datasets_dir()}"
    )
