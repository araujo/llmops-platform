"""Plugin entry: ``register()`` for ``llmops.agent_plugins`` — wires subpackages only."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter

from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.prompts import PromptSeedDocument
from llmops_core.plugins.protocol import AgentPlugin

from shopping_assistant.app.router import build_agent_router
from shopping_assistant.bootstrap.lifecycle import run_shutdown, run_startup
from shopping_assistant.constants import AGENT_ID
from shopping_assistant.prompts.seeds import load_prompt_seeds
from shopping_assistant.version import get_package_version


class ShoppingAssistantPlugin:
    """Integrates with the host exclusively via :class:`~llmops_core.plugins.protocol.AgentPlugin`."""

    def __init__(self) -> None:
        self._version = get_package_version()
        self._router = build_agent_router()
        self._seeds = tuple(load_prompt_seeds())

    @property
    def agent_id(self) -> str:
        return AGENT_ID

    @property
    def version(self) -> str:
        return self._version

    def routers(self) -> Sequence[APIRouter]:
        return (self._router,)

    def prompt_seeds(self) -> Sequence[PromptSeedDocument]:
        return self._seeds

    async def on_startup(self, ctx: AgentHostContext) -> None:
        await run_startup(ctx)

    async def on_shutdown(self, ctx: AgentHostContext) -> None:
        await run_shutdown(ctx)


def register() -> AgentPlugin:
    """Entry point declared in ``pyproject.toml`` under ``llmops.agent_plugins``."""
    return ShoppingAssistantPlugin()
