"""Abstract prompt persistence (no storage or domain specifics)."""

from __future__ import annotations

from typing import Protocol

from llmops_core.prompts.models import PromptStatus, PromptVersionRecord


class PromptRepository(Protocol):
    """Persistence port for versioned prompts keyed by agent namespace + name + version."""

    def upsert_version(self, record: PromptVersionRecord) -> PromptVersionRecord:
        """Insert or replace the row for ``(agent_id, name, version)``."""

    def get_version(self, agent_id: str, name: str, version: int) -> PromptVersionRecord | None:
        """Fetch a single revision."""

    def get_active(self, agent_id: str, name: str) -> PromptVersionRecord | None:
        """Return the active revision for this agent+name, if any."""

    def list_versions(self, agent_id: str, name: str) -> list[PromptVersionRecord]:
        """List all versions for an agent+name, sorted by ``version`` ascending."""

    def activate_version(self, agent_id: str, name: str, version: int) -> None:
        """Mark ``version`` active and all other versions for the same agent+name inactive."""

    def deactivate_all(self, agent_id: str, name: str) -> None:
        """Set every version for this agent+name to inactive."""
