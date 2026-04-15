"""Bootstrap shopping prompts into MongoDB using ``llmops-core`` repositories."""

from __future__ import annotations

from pymongo import MongoClient

from llmops_core.prompts import MongoPromptRepository, seed_prompts_from_seeds
from llmops_core.prompts.models import PromptVersionRecord

from shopping_assistant.constants import AGENT_ID
from shopping_assistant.prompts.catalog import build_shopping_prompt_seeds


def seed_shopping_prompts_to_mongo(
    mongo_uri: str,
    database: str,
    *,
    collection: str = "llmops_prompt_versions",
    activate: bool = True,
) -> list[PromptVersionRecord]:
    """Create/update prompt version rows for this agent (idempotent upserts + activation)."""
    client = MongoClient(mongo_uri)
    try:
        repo = MongoPromptRepository(client, database, collection=collection)
        repo.ensure_indexes()
        return seed_prompts_from_seeds(
            repo,
            AGENT_ID,
            build_shopping_prompt_seeds(),
            activate=activate,
        )
    finally:
        client.close()
