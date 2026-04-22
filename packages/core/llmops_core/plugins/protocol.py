"""Agent plugin protocol and lifecycle hook types."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from fastapi import APIRouter

from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.prompts import PromptSeedDocument

# --- Lifecycle hook aliases (host may also register these independently) ---

AgentStartupHook = Callable[[AgentHostContext], Awaitable[None]]
"""Async callback invoked once per plugin at application startup."""

AgentShutdownHook = Callable[[AgentHostContext], Awaitable[None]]
"""Async callback invoked once per plugin at application shutdown."""


class AgentPlugin(Protocol):
    """Structural contract for an agent package (agent-agnostic).

    The host depends only on this protocol (and related types), never on
    agent-specific modules. Implementations live in agent packages.

    **Required surface** (validated by
    :func:`llmops_core.plugins.registry.validate_plugin`):

    - ``agent_id``, ``version``
    - ``routers()``, ``prompt_seeds()``
    - ``on_startup``, ``on_shutdown``

    **Optional infrastructure** (not part of this protocol; agents may subclass
    :class:`llmops_core.plugins.base.BaseAgentPlugin` for defaults): trace
    metadata, :class:`~llmops_core.plugins.evals.AgentEvalRunner`, extra
    lifecycle hooks, alternate seed accessors.
    """

    @property
    def agent_id(self) -> str:
        """Unique slug used in URLs, config, and storage namespacing."""

    @property
    def version(self) -> str:
        """Plugin version string for logs, diagnostics, and compatibility."""

    def routers(self) -> Sequence[APIRouter]:
        """HTTP surface for this agent (prefixes set on each router)."""

    def prompt_seeds(self) -> Sequence[PromptSeedDocument]:
        """Prompt documents the host may seed (e.g. MongoDB)."""

    async def on_startup(self, ctx: AgentHostContext) -> None:
        """After ``ctx`` is built; pools, caches, warm-up."""

    async def on_shutdown(self, ctx: AgentHostContext) -> None:
        """Before process exit; flush clients and release resources."""
