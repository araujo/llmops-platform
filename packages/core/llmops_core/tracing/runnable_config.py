"""Runnable config fragments for LangChain / LangGraph (callbacks, tags, metadata)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


def merge_callbacks(
    *handlers: BaseCallbackHandler | None,
) -> list[BaseCallbackHandler]:
    """Drop ``None`` values; return a list for ``config['callbacks']``."""
    return [h for h in handlers if h is not None]


def build_runnable_config(
    *,
    callbacks: Sequence[BaseCallbackHandler] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dict for ``invoke`` / ``ainvoke`` ``config`` (LangChain + LangGraph).

    Example::

        chain.invoke(
            {"input": "hello"},
            config=build_runnable_config(
                callbacks=[handler],
                metadata={"request_id": "..."},
            ),
        )
    """
    cfg: dict[str, Any] = {}
    if callbacks:
        cfg["callbacks"] = list(callbacks)
    if tags is not None:
        cfg["tags"] = tags
    if metadata is not None:
        cfg["metadata"] = metadata
    return cfg
