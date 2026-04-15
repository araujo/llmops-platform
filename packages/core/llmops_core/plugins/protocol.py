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
    """Structural contract for an agent package.

    The host depends only on this protocol (and related types), never on
    agent-specific modules. Implementations live in agent packages.
    """

    @property
    def agent_id(self) -> str:
        """Unique slug used in URLs, config, and storage namespacing."""

    @property
    def version(self) -> str:
        """Plugin version string for logs, diagnostics, and compatibility checks."""

    def routers(self) -> Sequence[APIRouter]:
        """Optional HTTP surface contributed by this agent (prefixes set on each router)."""

    def prompt_seeds(self) -> Sequence[PromptSeedDocument]:
        """Prompt documents the host may seed into the prompt store (e.g. MongoDB)."""

    async def on_startup(self, ctx: AgentHostContext) -> None:
        """Called after the host has built ``ctx``; use for pools, caches, warm-up."""

    async def on_shutdown(self, ctx: AgentHostContext) -> None:
        """Called before process exit; flush clients and release resources."""
