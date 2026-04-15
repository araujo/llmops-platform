"""In-process cache over :class:`~llmops_core.prompts.repository.PromptRepository` for active prompts."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from llmops_core.prompts.models import PromptVersionRecord

if TYPE_CHECKING:
    from llmops_core.prompts.repository import PromptRepository


class PromptRegistry:
    """Resolves the active prompt for ``(agent_id, name)`` via a repository, with optional TTL cache."""

    def __init__(
        self,
        repository: PromptRepository,
        *,
        default_ttl_seconds: float = 0.0,
    ) -> None:
        self._repo = repository
        self._ttl = default_ttl_seconds
        self._cache: dict[tuple[str, str], tuple[PromptVersionRecord | None, float]] = {}

    def get_active(self, agent_id: str, name: str) -> PromptVersionRecord | None:
        """Return the active revision, using cache when ``default_ttl_seconds`` > 0."""
        key = (agent_id, name)
        now = time.monotonic()
        if self._ttl > 0 and key in self._cache:
            record, ts = self._cache[key]
            if now - ts < self._ttl:
                return record

        record = self._repo.get_active(agent_id, name)
        if self._ttl > 0:
            self._cache[key] = (record, now)
        return record

    def invalidate(self, agent_id: str, name: str) -> None:
        """Drop one cache entry after writes that change the active revision."""
        self._cache.pop((agent_id, name), None)

    def clear(self) -> None:
        """Drop all cached entries."""
        self._cache.clear()
