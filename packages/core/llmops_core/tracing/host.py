"""Host-level tracing bootstrap (Langfuse optional, environment-driven).

No agent names or domains here—callers attach agent-specific tags via
:meth:`llmops_core.plugins.base.BaseAgentPlugin.build_trace_metadata`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from llmops_core.tracing.langfuse import LangfuseClientConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TracingExtras:
    """Generic tracing state placed on host context extras."""

    enabled: bool
    """True when Langfuse callback tracing is configured."""

    langfuse_client: Any | None = None
    """Reserved for integrations that need a direct client."""

    langfuse_config: LangfuseClientConfig | None = None
    """Public, non-agent-specific Langfuse callback configuration."""


def load_tracing_extras_from_env() -> TracingExtras:
    """Create Langfuse callback config from env keys.

    Uses ``LANGFUSE_PUBLIC_KEY`` / ``LANGFUSE_SECRET_KEY`` (and optional host
    URL). If keys are absent, returns ``TracingExtras(enabled=False)`` without
    raising. The host deliberately does not instantiate ``langfuse.Langfuse``
    here because newer SDK clients configure OpenTelemetry exporters that are
    not supported by the local Langfuse v2 container.

    Set ``LLMOPS_TRACING_ENABLED`` to ``0`` / ``false`` / ``no`` to skip client
    creation even when Langfuse keys are present.
    """
    disabled = os.getenv("LLMOPS_TRACING_ENABLED", "").lower() in (
        "0",
        "false",
        "no",
    )
    if disabled:
        logger.info("Langfuse tracing disabled by LLMOPS_TRACING_ENABLED")
        return TracingExtras(enabled=False, langfuse_client=None)
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    if not pub or not sec:
        logger.info("Langfuse tracing disabled; public/secret key is missing")
        return TracingExtras(enabled=False, langfuse_client=None)
    cfg = LangfuseClientConfig(
        public_key=pub,
        secret_key=sec,
        host=os.getenv("LANGFUSE_HOST"),
        base_url=os.getenv("LANGFUSE_BASE_URL"),
    )
    logger.info(
        "Langfuse tracing enabled via LangChain callback; host=%s",
        cfg.host or cfg.base_url or "sdk default",
    )
    return TracingExtras(
        enabled=True,
        langfuse_client=None,
        langfuse_config=cfg,
    )
