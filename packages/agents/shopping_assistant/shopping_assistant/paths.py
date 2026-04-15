"""Canonical filesystem layout for shopping ops (package-local only).

Paths resolve under the ``shopping_assistant`` package tree, not the repo root.
Use from CLIs, evals, and bootstrap code.
"""

from __future__ import annotations

from pathlib import Path

# Root of the ``shopping_assistant`` package (``data/``, ``evals/``, ...).
PACKAGE_ROOT: Path = Path(__file__).resolve().parent


def package_root() -> Path:
    """Return ``shopping_assistant/`` directory."""
    return PACKAGE_ROOT


def data_dir() -> Path:
    """``shopping_assistant/data/``."""
    return PACKAGE_ROOT / "data"


def data_raw_dir() -> Path:
    """``data/raw/`` — vendor or downloaded catalog dumps."""
    return data_dir() / "raw"


def data_enriched_dir() -> Path:
    """``data/enriched/`` — normalized or joined catalog outputs."""
    return data_dir() / "enriched"


def data_samples_dir() -> Path:
    """``shopping_assistant/data/samples/`` — small fixtures for dev/tests."""
    return data_dir() / "samples"


def evals_dir() -> Path:
    """``shopping_assistant/evals/``."""
    return PACKAGE_ROOT / "evals"


def evals_datasets_dir() -> Path:
    """``evals/datasets/`` — eval inputs (JSONL/CSV), package-local."""
    return evals_dir() / "datasets"


def ensure_operational_dirs() -> None:
    """Create expected directories if missing (safe for first-run CLIs)."""
    for p in (
        data_raw_dir(),
        data_enriched_dir(),
        data_samples_dir(),
        evals_datasets_dir(),
    ):
        p.mkdir(parents=True, exist_ok=True)
