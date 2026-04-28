"""Startup/shutdown hooks for the shopping assistant (plugin only)."""

from __future__ import annotations

from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.infra import EXTRA_KEY_TRACING
from llmops_core.tracing.host import TracingExtras


async def run_startup(ctx: AgentHostContext) -> None:
    """Optional warm-up: log and check host services in ``ctx.extras``."""
    ctx.logger.info(
        "shopping_assistant startup",
        extra={"agent_id": ctx.agent_id},
    )
    if ctx.extras.get("prompt_registry") is not None:
        ctx.logger.debug("Host prompt registry available in extras")
    if ctx.extras.get("prompt_repository") is not None:
        ctx.logger.debug("Host prompt repository available in extras")
    tracing = ctx.extras.get(EXTRA_KEY_TRACING)
    if isinstance(tracing, TracingExtras) and tracing.enabled:
        ctx.logger.debug(
            "Host tracing extras present (Langfuse callback available)",
        )


async def run_shutdown(ctx: AgentHostContext) -> None:
    """Release resources if needed (placeholder for future clients/pools)."""
    ctx.logger.info(
        "shopping_assistant shutdown",
        extra={"agent_id": ctx.agent_id},
    )
