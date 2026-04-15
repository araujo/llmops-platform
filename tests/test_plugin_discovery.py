"""Tests for ``llmops-core`` plugin registry and entry-point discovery."""

from __future__ import annotations

from llmops_core.plugins.registry import ENTRY_POINT_GROUP, AgentRegistry


def test_entry_point_group_name() -> None:
    assert ENTRY_POINT_GROUP == "llmops.agent_plugins"


def test_discover_loads_shopping_assistant() -> None:
    registry = AgentRegistry.discover()
    assert "shopping_assistant" in registry
    plugin = registry.get("shopping_assistant")
    assert plugin is not None
    assert plugin.agent_id == "shopping_assistant"
    assert plugin.version
    routers = list(plugin.routers())
    assert len(routers) >= 1
    seeds = list(plugin.prompt_seeds())
    assert len(seeds) >= 1


def test_discovered_agent_ids_are_unique() -> None:
    seen: set[str] = set()
    for agent_id, _ in AgentRegistry.discover().items():
        assert agent_id not in seen
        seen.add(agent_id)
