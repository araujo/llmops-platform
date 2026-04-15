"""Langfuse client and LangChain/LangGraph callback helpers (no agent assumptions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from llmops_core.tracing.runnable_config import build_runnable_config


@dataclass(frozen=True, slots=True)
class LangfuseClientConfig:
    """Subset of :class:`langfuse.Langfuse` kwargs for explicit, typed wiring."""

    public_key: str | None = None
    secret_key: str | None = None
    base_url: str | None = None
    host: str | None = None
    timeout: int | None = None
    tracing_enabled: bool | None = None
    release: str | None = None
    environment: str | None = None
    sample_rate: float | None = None
    additional_headers: dict[str, str] | None = None


def create_langfuse_client(
    config: LangfuseClientConfig | None = None,
    **kwargs: Any,
) -> Langfuse:
    """Instantiate :class:`langfuse.Langfuse` from a dataclass and/or arbitrary kwargs.

    Unknown kwargs are forwarded to the client; callers control keys and env usage.
    """
    merged: dict[str, Any] = {}
    if config is not None:
        merged.update(
            {
                k: v
                for k, v in {
                    "public_key": config.public_key,
                    "secret_key": config.secret_key,
                    "base_url": config.base_url,
                    "host": config.host,
                    "timeout": config.timeout,
                    "tracing_enabled": config.tracing_enabled,
                    "release": config.release,
                    "environment": config.environment,
                    "sample_rate": config.sample_rate,
                    "additional_headers": config.additional_headers,
                }.items()
                if v is not None
            }
        )
    merged.update(kwargs)
    return Langfuse(**merged)


def create_langfuse_callback_handler(
    *,
    public_key: str | None = None,
    trace_context: dict[str, Any] | None = None,
) -> CallbackHandler:
    """Build :class:`langfuse.langchain.CallbackHandler` for LangChain / LangGraph runs.

    When ``public_key`` is omitted, Langfuse uses its default client configuration
    (typically environment-driven). ``trace_context`` can carry ``trace_id`` / parent ids.
    """
    return CallbackHandler(public_key=public_key, trace_context=trace_context)


def langfuse_run_config(
    *,
    callback: CallbackHandler | None = None,
    callbacks: list[CallbackHandler] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Runnable ``config`` dict including Langfuse callback(s)."""
    cbs: list[Any] = []
    if callback is not None:
        cbs.append(callback)
    if callbacks:
        cbs.extend(callbacks)
    return build_runnable_config(callbacks=cbs if cbs else None, tags=tags, metadata=metadata)
