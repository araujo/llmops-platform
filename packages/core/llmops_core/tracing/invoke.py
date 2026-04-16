"""LangChain ``invoke`` config from host tracing + plugin trace metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.infra import merge_agent_trace_metadata
from llmops_core.tracing.host import TracingExtras
from llmops_core.tracing.langfuse import (
    create_langfuse_callback_handler,
    langfuse_run_config,
)


def build_langfuse_llm_invoke_config(
    tracing_extras: TracingExtras | None,
    plugin: object,
    *,
    base_metadata: Mapping[str, Any] | None = None,
    ctx: AgentHostContext | None = None,
    **trace_metadata_kwargs: Any,
) -> dict[str, Any] | None:
    """Build a LangChain ``config`` for ``llm.invoke`` when Langfuse is on.

    Merges host ``base_metadata`` with ``plugin.build_trace_metadata(...)``
    via :func:`merge_agent_trace_metadata`. Returns ``None`` when tracing is
    off or no Langfuse client was created.
    """
    if tracing_extras is None or not tracing_extras.enabled:
        return None
    if tracing_extras.langfuse_client is None:
        return None
    meta = merge_agent_trace_metadata(
        plugin,
        base=base_metadata,
        ctx=ctx,
        **trace_metadata_kwargs,
    )
    handler = create_langfuse_callback_handler()
    return langfuse_run_config(callback=handler, metadata=meta or {})
