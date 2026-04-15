"""Prompt seed payloads for host-side persistence (e.g. MongoDB)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptSeedDocument:
    """Immutable prompt definition the host may insert or upsert during migrations.

    The owning plugin's ``agent_id`` is applied by the host when writing to storage.
    """

    name: str
    """Logical prompt name within the agent (host may namespace by agent_id)."""

    template: str
    """Prompt body (plain text, Jinja, etc.—interpretation is agent-specific)."""

    version: int = 1
    """Monotonic or declared version number for this seed document."""

    labels: tuple[str, ...] = ()
    """e.g. ``\"production\"``, ``\"canary\"``—host may map to Mongo labels."""

    model_defaults: dict[str, Any] = field(default_factory=dict)
    """Optional default model parameters for this prompt."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Arbitrary metadata (authoring tool, source commit, etc.)."""
