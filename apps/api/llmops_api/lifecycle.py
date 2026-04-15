"""Application lifespan: shared services, plugin discovery, prompts, hooks, routers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pymongo import MongoClient

from llmops_api.context import build_host_context
from llmops_api.settings import Settings
from llmops_core.plugins.registry import AgentRegistry
from llmops_core.prompts import (
    MongoPromptRepository,
    PromptRegistry,
    PromptRepository,
    seed_prompts_from_seeds,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    app.state.settings = settings

    mongo_client: MongoClient | None = None
    prompt_repository: PromptRepository | None = None
    prompt_registry: PromptRegistry | None = None

    if settings.mongo_uri:
        mongo_client = MongoClient(settings.mongo_uri)
        prompt_repository = MongoPromptRepository(
            mongo_client,
            settings.mongo_database,
            collection=settings.mongo_prompt_collection,
        )
        prompt_repository.ensure_indexes()
        prompt_registry = PromptRegistry(prompt_repository)

    app.state.mongo_client = mongo_client
    app.state.prompt_repository = prompt_repository
    app.state.prompt_registry = prompt_registry

    if settings.skip_plugin_discovery:
        agent_registry = AgentRegistry({})
        logger.warning("Plugin discovery skipped (LLMOPS_SKIP_PLUGIN_DISCOVERY=1)")
    else:
        agent_registry = AgentRegistry.discover()
    app.state.agent_registry = agent_registry

    if settings.seed_prompts_on_startup and prompt_repository is not None:
        for agent_id, plugin in agent_registry.items():
            seeds = list(plugin.prompt_seeds())
            if not seeds:
                continue
            seed_prompts_from_seeds(
                prompt_repository,
                agent_id,
                seeds,
                activate=True,
            )
        if prompt_registry is not None:
            prompt_registry.clear()

    for agent_id, plugin in agent_registry.items():
        log = logging.getLogger(f"llmops.agent.{agent_id}")
        extras: dict[str, Any] = {}
        if prompt_registry is not None:
            extras["prompt_registry"] = prompt_registry
        if prompt_repository is not None:
            extras["prompt_repository"] = prompt_repository
        ctx = build_host_context(
            agent_id=agent_id,
            settings=settings,
            logger=log,
            extras=extras,
        )
        await plugin.on_startup(ctx)

    _register_plugin_routers(app, agent_registry)

    yield

    for agent_id, plugin in reversed(list(agent_registry.items())):
        log = logging.getLogger(f"llmops.agent.{agent_id}")
        extras = {}
        pr = app.state.prompt_registry
        if pr is not None:
            extras["prompt_registry"] = pr
        pq = app.state.prompt_repository
        if pq is not None:
            extras["prompt_repository"] = pq
        ctx = build_host_context(
            agent_id=agent_id,
            settings=settings,
            logger=log,
            extras=extras,
        )
        await plugin.on_shutdown(ctx)

    if mongo_client is not None:
        mongo_client.close()


def _register_plugin_routers(app: FastAPI, agent_registry: AgentRegistry) -> None:
    """Mount each plugin's routers under ``/v1/agents/{agent_id}``."""
    for agent_id, router in agent_registry.iter_routers():
        app.include_router(router, prefix=f"/v1/agents/{agent_id}")
