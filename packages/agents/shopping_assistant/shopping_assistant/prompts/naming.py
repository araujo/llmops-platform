"""Qualified prompt ids for shopping prompts (agent-local convention).

MongoDB rows use ``(agent_id, name, version)`` with a short ``name`` (``system``,
``product_search``). The dotted id ``shopping_assistant.<name>`` is stored in
``metadata.qualified_name`` for cross-system references.

Example document::

    agent_id: shopping_assistant
    name: system
    version: 1
    metadata.qualified_name: shopping_assistant.system

Versioning:
- Bump ``version`` when the template changes materially.
- The shared seeder upserts the triple and can activate the revision.
"""

from __future__ import annotations


def qualified_prompt_id(agent_id: str, short_name: str) -> str:
    """Return ``{agent_id}.{short_name}`` (e.g. ``shopping_assistant.system``)."""
    return f"{agent_id}.{short_name}"
