"""Generic eval-runner contract (datasets and scoring live in each agent)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AgentEvalRunner(Protocol):
    """Offline eval handle from :meth:`BaseAgentPlugin.get_eval_runner`.

    Agents implement this protocol; each agent defines suite format and rules.
    """

    def list_datasets(self) -> list[Path]:
        """Dataset files this runner can execute (package-local paths)."""

    def run_suite(self, dataset_stem: str) -> Mapping[str, Any]:
        """Run suite ``{stem}.json``; return JSON-serializable summaries."""
