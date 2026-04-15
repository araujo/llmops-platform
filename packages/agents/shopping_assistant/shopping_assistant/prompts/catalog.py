"""Build ``PromptSeedDocument`` rows from packaged ``.txt`` templates."""

from __future__ import annotations

from importlib import resources
from typing import Any

from llmops_core.plugins.prompts import PromptSeedDocument

from shopping_assistant.constants import AGENT_ID
from shopping_assistant.prompts.naming import qualified_prompt_id


def _read_template(pkg: Any, filename: str) -> str:
    node = pkg.joinpath(filename)
    return node.read_text(encoding="utf-8").strip() + "\n"


def build_shopping_prompt_seeds() -> tuple[PromptSeedDocument, ...]:
    """Return all shopping seeds (short ``name``; ``qualified_name`` in metadata)."""
    pkg = resources.files("shopping_assistant.prompts.documents")

    system_template = _read_template(pkg, "system.txt")
    product_search_template = _read_template(pkg, "product_search.txt")

    meta_system: dict[str, Any] = {
        "qualified_name": qualified_prompt_id(AGENT_ID, "system"),
        "kind": "system",
    }
    meta_search: dict[str, Any] = {
        "qualified_name": qualified_prompt_id(AGENT_ID, "product_search"),
        "kind": "product_search",
    }

    return (
        PromptSeedDocument(
            name="system",
            version=1,
            template=system_template,
            labels=("production",),
            metadata=meta_system,
        ),
        PromptSeedDocument(
            name="product_search",
            version=1,
            template=product_search_template,
            labels=("production",),
            metadata=meta_search,
        ),
    )
