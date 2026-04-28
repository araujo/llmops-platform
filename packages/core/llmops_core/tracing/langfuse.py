"""Langfuse client and LangChain/LangGraph callback helpers (no agent assumptions)."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

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
) -> Any:
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
    from langfuse import Langfuse

    return Langfuse(**merged)


def _callback_handler_class() -> Any:
    """Return the Langfuse LangChain callback class for the installed SDK."""
    try:
        from langfuse.callback import CallbackHandler
    except ModuleNotFoundError:
        from langfuse.langchain import CallbackHandler

    return CallbackHandler


def create_langfuse_callback_handler(
    *,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
    base_url: str | None = None,
    trace_context: dict[str, Any] | None = None,
) -> Any:
    """Build Langfuse's LangChain callback for the installed SDK version.

    Langfuse SDK v2 exposes ``langfuse.callback.CallbackHandler`` and accepts
    host/secret key directly. Newer SDKs expose ``langfuse.langchain`` and read
    some values from the environment; unsupported kwargs are intentionally
    omitted so this helper remains version-tolerant.
    """
    handler_cls = _callback_handler_class()
    sig = inspect.signature(handler_cls)
    supported = sig.parameters
    kwargs: dict[str, Any] = {}
    endpoint = host or base_url
    if public_key is not None and "public_key" in supported:
        kwargs["public_key"] = public_key
    if secret_key is not None and "secret_key" in supported:
        kwargs["secret_key"] = secret_key
    if endpoint is not None and "host" in supported:
        kwargs["host"] = endpoint
    if endpoint is not None and "base_url" in supported:
        kwargs["base_url"] = endpoint
    if trace_context is not None and "trace_context" in supported:
        kwargs["trace_context"] = trace_context
    return handler_cls(**kwargs)


def langfuse_run_config(
    *,
    callback: Any | None = None,
    callbacks: list[Any] | None = None,
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
