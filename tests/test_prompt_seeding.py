"""Prompt seeds, registry, and host behavior with/without Mongo."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from llmops_core.prompts import (
    PromptRegistry,
    namespaced_prompt_label,
    seed_prompts_from_seeds,
)
from llmops_core.prompts.models import PromptStatus
from shopping_assistant.constants import AGENT_ID
from shopping_assistant.plugin import ShoppingAssistantPlugin
from shopping_assistant.prompts.naming import qualified_prompt_id
from shopping_assistant.prompts.seeds import load_prompt_seeds

from in_memory_prompt_repository import InMemoryPromptRepository


@pytest.fixture
def client_no_mongo(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """ASGI app with ``LLMOPS_MONGO_URI`` unset so the host has no prompt repository."""
    monkeypatch.delenv("LLMOPS_MONGO_URI", raising=False)
    from llmops_api.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_shopping_load_prompt_seeds_returns_prompt_seed_documents() -> None:
    seeds = list(load_prompt_seeds())
    assert len(seeds) == 2
    names = {s.name for s in seeds}
    assert names == {"system", "product_search"}
    for s in seeds:
        assert s.template.strip()
        assert s.version >= 1
        assert "qualified_name" in s.metadata


def test_namespaced_prompt_label_and_qualified_metadata() -> None:
    assert namespaced_prompt_label(AGENT_ID, "system") == "shopping_assistant/system"
    seeds = load_prompt_seeds()
    by_name = {s.name: s for s in seeds}
    assert by_name["system"].metadata.get("qualified_name") == qualified_prompt_id(
        AGENT_ID, "system"
    )
    assert by_name["product_search"].metadata.get("qualified_name") == qualified_prompt_id(
        AGENT_ID, "product_search"
    )


def test_seed_prompts_from_seeds_in_memory_repository() -> None:
    repo = InMemoryPromptRepository()
    seeds = list(load_prompt_seeds())
    records = seed_prompts_from_seeds(repo, AGENT_ID, seeds, activate=True)
    assert len(records) == 2
    for r in records:
        assert r.agent_id == AGENT_ID
        assert r.status == PromptStatus.ACTIVE
        assert repo.get_active(AGENT_ID, r.name) is not None


def test_prompt_registry_resolves_active_after_seeding() -> None:
    """``PromptRegistry`` only needs a :class:`PromptRepository` implementation."""
    repo = InMemoryPromptRepository()
    seeds = list(load_prompt_seeds())
    seed_prompts_from_seeds(repo, AGENT_ID, seeds, activate=True)
    registry = PromptRegistry(repo)
    active = registry.get_active(AGENT_ID, "system")
    assert active is not None
    assert active.status == PromptStatus.ACTIVE
    assert "shopping" in active.template.lower()


def test_shopping_plugin_exposes_seeds_without_mongo() -> None:
    """Seeds are defined in-package; persistence is optional."""
    plugin = ShoppingAssistantPlugin()
    seeds = list(plugin.prompt_seeds())
    assert len(seeds) >= 2


def test_host_starts_without_mongo_plugin_seeds_still_available(
    client_no_mongo: TestClient,
) -> None:
    """mongo_uri=None: no repository/registry; agent still carries seed documents."""
    client_no_mongo.get("/health")
    app = client_no_mongo.app
    assert app.state.prompt_repository is None
    assert app.state.prompt_registry is None
    assert app.state.mongo_client is None

    plugin = app.state.agent_registry.get("shopping_assistant")
    assert plugin is not None
    seeds = list(plugin.prompt_seeds())
    assert len(seeds) >= 2
    assert {s.name for s in seeds} == {"system", "product_search"}


@pytest.mark.integration
def test_mongo_repository_optional_roundtrip() -> None:
    """Real MongoDB only when ``LLMOPS_MONGO_URI`` is set (e.g. local docker)."""
    uri = os.environ.get("LLMOPS_MONGO_URI")
    if not uri:
        pytest.skip("LLMOPS_MONGO_URI not set; start Mongo or export URI to run.")

    from pymongo import MongoClient

    from llmops_core.prompts import MongoPromptRepository

    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")

    db_name = os.environ.get("LLMOPS_MONGO_DATABASE", "llmops_test_prompt_seeding")
    coll = f"test_prompt_versions_{os.getpid()}"
    repo = MongoPromptRepository(client, db_name, collection=coll)
    repo.ensure_indexes()

    try:
        seeds = list(load_prompt_seeds())
        seed_prompts_from_seeds(repo, AGENT_ID, seeds, activate=True)
        got = repo.get_active(AGENT_ID, "system")
        assert got is not None
        assert got.status.value == "active"
    finally:
        client[db_name][coll].drop()
        client.close()
