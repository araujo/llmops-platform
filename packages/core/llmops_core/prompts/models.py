"""Domain models for versioned prompts (agent-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class PromptStatus(StrEnum):
    """Lifecycle flag for a specific prompt version row."""

    ACTIVE = "active"
    INACTIVE = "inactive"


def namespaced_prompt_label(agent_id: str, name: str) -> str:
    """Stable human-readable id: ``{agent_id}/{name}`` (not used as a DB primary key)."""
    return f"{agent_id}/{name}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class PromptVersionRecord:
    """One immutable version of a prompt, stored as a single MongoDB document.

    Uniqueness is ``(agent_id, name, version)``. At most one version per
    ``(agent_id, name)`` should be :class:`PromptStatus.ACTIVE` at a time; the
    repository enforces that when activating a version.
    """

    agent_id: str
    """Owning agent (namespace)."""

    name: str
    """Logical prompt name within the agent (short id, not prefixed with agent_id)."""

    version: int
    """Monotonic version number for this agent+name pair."""

    status: PromptStatus
    """Whether this row is the selectable \"active\" revision for resolve."""

    template: str
    """Prompt body (plain text, Jinja, etc.—interpretation is agent-specific)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary metadata (author, source, labels echo, etc.)."""

    model_defaults: dict[str, Any] = field(default_factory=dict)
    """Default model parameters for this revision."""

    labels: tuple[str, ...] = ()
    """Optional labels (e.g. environment or cohort), stored for auditing."""

    created_at: datetime = field(default_factory=utcnow)
    """UTC creation time for this revision row."""

    document_id: str | None = None
    """MongoDB ``_id`` as string when read from storage."""
