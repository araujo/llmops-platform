"""Plugin entry: ``register()`` for ``llmops.agent_plugins`` — wires subpackages only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import APIRouter

from llmops_core.plugins.base import BaseAgentPlugin
from llmops_core.plugins.evals import AgentEvalRunner
from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.prompts import PromptSeedDocument
from llmops_core.plugins.protocol import AgentPlugin

from shopping_assistant.app.router import build_agent_router
from shopping_assistant.bootstrap.lifecycle import run_shutdown, run_startup
from shopping_assistant.constants import AGENT_ID
from shopping_assistant.infra.eval_runner import ShoppingEvalRunner
from shopping_assistant.prompts.seeds import load_prompt_seeds
from shopping_assistant.version import get_package_version


class ShoppingAssistantPlugin(BaseAgentPlugin):
    """Shopping agent: extends :class:`~llmops_core.plugins.base.BaseAgentPlugin`.

    Required plugin surface is implemented here; optional tracing/eval hooks use
    base-class defaults until shopping-specific infra overrides them.
    """

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

    def build_trace_metadata(
        self,
        *,
        ctx: AgentHostContext | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any] | None:
        return {"agent_id": self.agent_id, "domain": "shopping"}

    def get_eval_runner(self) -> AgentEvalRunner:
        return ShoppingEvalRunner()


def register() -> AgentPlugin:
    """Entry point declared in ``pyproject.toml`` under ``llmops.agent_plugins``."""
    return ShoppingAssistantPlugin()
