"""Concrete ``AgentHostContext`` implementation for the API host."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from llmops_api.settings import Settings


class SimpleAgentHostContext:
    """Per-agent lifecycle context: identity, logger, and ``extras`` bag."""

    def __init__(
        self,
        *,
        agent_id: str,
        logger: logging.Logger,
        extras: Mapping[str, Any],
    ) -> None:
        self._agent_id = agent_id
        self._logger = logger
        self._extras = extras

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @property
    def extras(self) -> Mapping[str, Any]:
        return self._extras


def build_host_context(
    *,
    agent_id: str,
    settings: Settings,
    logger: logging.Logger,
    extras: Mapping[str, Any] | None = None,
) -> SimpleAgentHostContext:
    """Merge ``settings`` into ``extras``; callers may pass more keys."""
    base: dict[str, Any] = {"settings": settings}
    if extras:
        base.update(dict(extras))
    return SimpleAgentHostContext(agent_id=agent_id, logger=logger, extras=base)
