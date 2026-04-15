"""Startup/shutdown hooks for the shopping assistant (called by the plugin only)."""

from __future__ import annotations

from llmops_core.plugins.context import AgentHostContext


async def run_startup(ctx: AgentHostContext) -> None:
    """Optional warm-up: logging and checking host-provided services in ``ctx.extras``."""
    ctx.logger.info("shopping_assistant startup", extra={"agent_id": ctx.agent_id})
    if ctx.extras.get("prompt_registry") is not None:
        ctx.logger.debug("Host prompt registry available in extras")
    if ctx.extras.get("prompt_repository") is not None:
        ctx.logger.debug("Host prompt repository available in extras")


async def run_shutdown(ctx: AgentHostContext) -> None:
    """Release resources if needed (placeholder for future clients/pools)."""
    ctx.logger.info("shopping_assistant shutdown", extra={"agent_id": ctx.agent_id})
