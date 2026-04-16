"""Agent infrastructure: ``extras`` keys and trace metadata merge helpers.

These utilities are agent-agnostic. Agent-specific tags belong in
:class:`~llmops_core.plugins.base.BaseAgentPlugin.build_trace_metadata`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from llmops_core.plugins.context import AgentHostContext

# Standard keys for :attr:`AgentHostContext.extras` (set by the API host).
EXTRA_KEY_TRACING = "llmops_tracing"
"""Value: :class:`~llmops_core.tracing.host.TracingExtras` from host init."""

EXTRA_KEY_EVAL_RUNNER = "eval_runner"
"""Value: optional eval handle from :meth:`BaseAgentPlugin.get_eval_runner`."""

# FastAPI ``app.state`` attribute (set by the API host lifecycle).
APP_STATE_ATTR_TRACING_EXTRAS = "llmops_tracing_extras"
"""Same :class:`~llmops_core.tracing.host.TracingExtras` as ``extras`` key."""


def merge_agent_trace_metadata(
    plugin: object,
    *,
    base: Mapping[str, Any] | None = None,
    ctx: AgentHostContext | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Merge host ``base`` metadata with the plugin's ``build_trace_metadata``.

    If the plugin does not implement ``build_trace_metadata``, returns a copy
    of ``base`` (or ``None`` if ``base`` is empty/None).
    """
    merged: dict[str, Any] = {}
    if base:
        merged.update(dict(base))
    fn = getattr(plugin, "build_trace_metadata", None)
    if callable(fn):
        if ctx is not None:
            extra = fn(ctx=ctx, **kwargs)
        else:
            extra = fn(**kwargs)
        if extra:
            merged.update(dict(extra))
    return merged if merged else None
