"""Optional base class for agent plugins (infra extension points with defaults).

The host validates plugins against
:class:`~llmops_core.plugins.protocol.AgentPlugin` (structural contract). This
module adds a concrete base class so agents inherit **required** hooks and get
**no-op defaults** for optional infrastructure (tracing metadata, eval runner,
extra lifecycle hooks) without ad-hoc methods per agent.

Nothing here is shopping-specific. Subclass :class:`BaseAgentPlugin` or
implement :class:`AgentPlugin` directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import APIRouter

from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.prompts import PromptSeedDocument
from llmops_core.plugins.protocol import AgentShutdownHook, AgentStartupHook


class BaseAgentPlugin(ABC):
    """Required plugin surface + optional infra no-ops.

    **Required** (subclass must implement — same as :class:`AgentPlugin`):

    - ``agent_id``, ``version``
    - ``routers()``, ``prompt_seeds()``
    - ``on_startup``, ``on_shutdown``

    **Optional** (defaults here; override when wiring tracing/eval later):

    - ``get_prompt_seed_documents()`` — defaults to ``prompt_seeds()``; override
      if the seeding document set should differ from ``prompt_seeds()``.
    - ``get_startup_hooks()`` / ``get_shutdown_hooks()`` — extra callables beyond
      ``on_startup`` / ``on_shutdown`` (empty by default). The host may compose
      these when multi-hook support exists; today the registry uses only
      ``on_startup`` / ``on_shutdown``.
    - ``build_trace_metadata()`` — small JSON-serializable dict for spans, or
      ``None`` to skip (default). Combine with host metadata via
      :func:`~llmops_core.plugins.infra.merge_agent_trace_metadata`.
    - ``get_eval_runner()`` — agent-specific eval runner, or ``None`` (default).
      Return type stays loose until eval infra exists.
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique slug (URLs, storage namespacing)."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string."""

    @abstractmethod
    def routers(self) -> Sequence[APIRouter]:
        """HTTP routers for this agent."""

    @abstractmethod
    def prompt_seeds(self) -> Sequence[PromptSeedDocument]:
        """Prompt seed documents for the host prompt store."""

    @abstractmethod
    async def on_startup(self, ctx: AgentHostContext) -> None:
        """Primary startup hook (called by the host lifecycle)."""

    @abstractmethod
    async def on_shutdown(self, ctx: AgentHostContext) -> None:
        """Primary shutdown hook (called by the host lifecycle)."""

    def get_prompt_seed_documents(self) -> Sequence[PromptSeedDocument]:
        """Documents to seed; default mirrors :meth:`prompt_seeds`."""
        return tuple(self.prompt_seeds())

    def get_startup_hooks(self) -> Sequence[AgentStartupHook]:
        """Optional extra startup hooks (beyond :meth:`on_startup`)."""
        return ()

    def get_shutdown_hooks(self) -> Sequence[AgentShutdownHook]:
        """Optional extra shutdown hooks (beyond :meth:`on_shutdown`)."""
        return ()

    def build_trace_metadata(
        self,
        *,
        ctx: AgentHostContext | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any] | None:
        """Metadata for tracing spans; ``None`` means omit."""
        return None

    def get_eval_runner(self) -> Any:
        """Eval runner instance, or ``None`` if not exposed."""
        return None
