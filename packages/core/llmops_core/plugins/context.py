"""Host-facing context passed into plugins (lifecycle and request paths)."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Protocol


class AgentHostContext(Protocol):
    """Services and identifiers the host supplies to agent plugins.

    The host implements this protocol. ``extras`` keeps core free of concrete
    integration types (Langfuse, Mongo, Postgres) while still allowing the
    host to pass them through to plugins that expect specific keys.
    """

    @property
    def agent_id(self) -> str:
        """Stable agent id (slug) for this plugin instance."""

    @property
    def logger(self) -> logging.Logger:
        """Logger scoped to this agent (or the request), as provided by the host."""

    @property
    def extras(self) -> Mapping[str, Any]:
        """Opaque bag of host integrations (clients, callbacks, settings snapshots).

        Conventional keys (all optional, set by the API host when applicable):

        - ``"settings"`` — host settings snapshot.
        - ``"prompt_registry"`` / ``"prompt_repository"`` — prompt store handles.
        - ``"llmops_tracing"`` — :class:`~llmops_core.tracing.host.TracingExtras`.
        - ``"eval_runner"`` — object from the active plugin's
          :meth:`~llmops_core.plugins.base.BaseAgentPlugin.get_eval_runner`.

        The API host also sets ``app.state.llmops_tracing_extras`` to the same
        :class:`~llmops_core.tracing.host.TracingExtras` for request paths that
        build per-run LangChain configs (see
        :func:`~llmops_core.tracing.invoke.build_langfuse_llm_invoke_config`).
        """
