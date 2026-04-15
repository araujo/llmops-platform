"""Prompt seed documents for host-side persistence (MongoDB via core)."""

from __future__ import annotations

from collections.abc import Sequence

from llmops_core.plugins.prompts import PromptSeedDocument

from shopping_assistant.prompts.catalog import build_shopping_prompt_seeds


def load_prompt_seeds() -> Sequence[PromptSeedDocument]:
    """Prompt revisions for this agent (Mongo keys: ``agent_id`` + short ``name`` + ``version``)."""
    return build_shopping_prompt_seeds()
