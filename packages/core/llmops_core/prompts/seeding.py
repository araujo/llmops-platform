"""Load plugin :class:`~llmops_core.plugins.prompts.PromptSeedDocument` rows into storage."""

from __future__ import annotations

from collections.abc import Sequence

from llmops_core.plugins.prompts import PromptSeedDocument
from llmops_core.prompts.models import PromptStatus, PromptVersionRecord, utcnow
from llmops_core.prompts.repository import PromptRepository


def seed_prompts_from_seeds(
    repository: PromptRepository,
    agent_id: str,
    seeds: Sequence[PromptSeedDocument],
    *,
    activate: bool = True,
) -> list[PromptVersionRecord]:
    """Insert or replace versions from plugin seeds and optionally activate each name.

    For each seed, upserts ``(agent_id, seed.name, seed.version)``. If ``activate``
    is true, the repository marks that version active and deactivates sibling
    versions for the same ``(agent_id, name)`` via
    :meth:`PromptRepository.activate_version` (idempotent for a single-version
    seed).
    """
    if not agent_id.strip():
        raise ValueError("agent_id must be non-empty")

    out: list[PromptVersionRecord] = []
    for seed in seeds:
        inactive = PromptStatus.INACTIVE
        record = PromptVersionRecord(
            agent_id=agent_id,
            name=seed.name,
            version=seed.version,
            status=inactive,
            template=seed.template,
            metadata=dict(seed.metadata),
            model_defaults=dict(seed.model_defaults),
            labels=tuple(seed.labels),
            created_at=utcnow(),
        )
        repository.upsert_version(record)
        if activate:
            repository.activate_version(agent_id, seed.name, seed.version)
        resolved = repository.get_version(agent_id, seed.name, seed.version)
        out.append(resolved if resolved is not None else record)
    return out
