"""Host-level tracing bootstrap (Langfuse optional, environment-driven).

No agent names or domains here—callers attach agent-specific tags via
:meth:`llmops_core.plugins.base.BaseAgentPlugin.build_trace_metadata`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from llmops_core.tracing.langfuse import LangfuseClientConfig, create_langfuse_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TracingExtras:
    """Generic tracing state placed on :attr:`AgentHostContext.extras` by the host."""

    enabled: bool
    """True when Langfuse client initialization succeeded."""

    langfuse_client: Any | None = None
    """``langfuse.Langfuse`` instance when enabled; else ``None``."""


def load_tracing_extras_from_env() -> TracingExtras:
    """Create a Langfuse client when env keys are set; otherwise disabled.

    Uses ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` (and optional host
    URL) the same way as the Langfuse SDK. If keys are absent or init fails,
    returns ``TracingExtras(enabled=False)`` without raising.

    Set ``LLMOPS_TRACING_ENABLED`` to ``0`` / ``false`` / ``no`` to skip client
    creation even when Langfuse keys are present.
    """
    disabled = os.getenv("LLMOPS_TRACING_ENABLED", "").lower() in (
        "0",
        "false",
        "no",
    )
    if disabled:
        return TracingExtras(enabled=False, langfuse_client=None)
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        return TracingExtras(enabled=False, langfuse_client=None)
    try:
        cfg = LangfuseClientConfig(
            public_key=pub,
            secret_key=sec,
            host=os.getenv("LANGFUSE_HOST"),
            base_url=os.getenv("LANGFUSE_BASE_URL"),
        )
        client = create_langfuse_client(cfg)
        return TracingExtras(enabled=True, langfuse_client=client)
    except Exception:
        logger.exception("Langfuse client init failed; tracing disabled")
        return TracingExtras(enabled=False, langfuse_client=None)
