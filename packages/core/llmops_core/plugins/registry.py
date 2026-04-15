"""Discover and validate agent plugins via ``importlib.metadata`` entry points."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from importlib.metadata import EntryPoint, entry_points
from typing import cast

from fastapi import APIRouter

from llmops_core.plugins.prompts import PromptSeedDocument
from llmops_core.plugins.protocol import (
    AgentPlugin,
    AgentShutdownHook,
    AgentStartupHook,
)

logger = logging.getLogger(__name__)

#: Group name for ``[project.entry-points."llmops.agent_plugins"]`` in agent packages.
ENTRY_POINT_GROUP = "llmops.agent_plugins"


class PluginLoadError(RuntimeError):
    """Raised when an entry point cannot be imported or its target cannot be loaded."""


class PluginValidationError(ValueError):
    """Raised when a loaded object does not satisfy :class:`AgentPlugin`."""


def _entry_points_in_group(group: str) -> tuple[EntryPoint, ...]:
    eps = entry_points()
    if hasattr(eps, "select"):
        return tuple(eps.select(group=group))
    # Python 3.9: mapping of group -> entry points
    if isinstance(eps, dict):
        return tuple(eps.get(group, ()))
    get = getattr(eps, "get", None)
    if callable(get):
        return tuple(get(group, ()))
    return ()


def _label(ep: EntryPoint) -> str:
    return f"{ep.name} = {ep.value}"


def coerce_plugin_object(loaded: object, *, where: str) -> AgentPlugin:
    """Turn an entry-point target (class, factory, or instance) into a plugin instance."""
    prefix = f"{where}: " if where else ""
    candidate: object

    if isinstance(loaded, type):
        try:
            candidate = loaded()
        except TypeError as e:
            raise PluginValidationError(
                f"{prefix}expected class {loaded!r} to be constructible with no arguments: {e}"
            ) from e
        except Exception as e:
            raise PluginLoadError(
                f"{prefix}constructor of class {loaded!r} raised unexpectedly: {e}"
            ) from e
    elif callable(loaded):
        try:
            candidate = loaded()
        except TypeError as e:
            raise PluginValidationError(
                f"{prefix}expected callable {loaded!r} to be invokable with no arguments: {e}"
            ) from e
        except Exception as e:
            raise PluginLoadError(
                f"{prefix}factory callable {loaded!r} raised unexpectedly: {e}"
            ) from e
    else:
        candidate = loaded

    validate_plugin(candidate, where=where)
    return cast(AgentPlugin, candidate)


def load_plugin_from_entry_point(ep: EntryPoint) -> AgentPlugin:
    """Load and validate the object advertised by a single entry point."""
    where = f"entry point {_label(ep)!r}"
    try:
        loaded = ep.load()
    except Exception as e:
        raise PluginLoadError(
            f"Failed to import entry point {_label(ep)!r} in group {ENTRY_POINT_GROUP!r}: {e}"
        ) from e
    return coerce_plugin_object(loaded, where=where)


def validate_plugin(obj: object, *, where: str = "") -> None:
    """Ensure ``obj`` structurally satisfies :class:`AgentPlugin`; raise otherwise."""
    prefix = f"{where}: " if where else ""

    if obj is None:
        raise PluginValidationError(f"{prefix}plugin object is None")

    if not hasattr(obj, "agent_id"):
        raise PluginValidationError(f"{prefix}missing required attribute 'agent_id'")
    agent_id = getattr(obj, "agent_id")
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise PluginValidationError(
            f"{prefix}agent_id must be a non-empty str, got {agent_id!r}"
        )

    if not hasattr(obj, "version"):
        raise PluginValidationError(f"{prefix}missing required attribute 'version'")
    version = getattr(obj, "version")
    if not isinstance(version, str):
        raise PluginValidationError(
            f"{prefix}version must be str, got {type(version).__name__}"
        )

    routers_fn = getattr(obj, "routers", None)
    if not callable(routers_fn):
        raise PluginValidationError(
            f"{prefix}routers must be callable, got {type(routers_fn).__name__!r}"
        )
    try:
        routers = routers_fn()
    except Exception as e:
        raise PluginValidationError(
            f"{prefix}routers() raised while validating: {e}"
        ) from e
    if not isinstance(routers, Sequence):
        raise PluginValidationError(
            f"{prefix}routers() must return a sequence, got {type(routers).__name__!r}"
        )
    for i, router in enumerate(routers):
        if not isinstance(router, APIRouter):
            raise PluginValidationError(
                f"{prefix}routers()[{i}] must be fastapi.APIRouter, got {type(router).__name__!r}"
            )

    seeds_fn = getattr(obj, "prompt_seeds", None)
    if not callable(seeds_fn):
        raise PluginValidationError(
            f"{prefix}prompt_seeds must be callable, got {type(seeds_fn).__name__!r}"
        )
    try:
        seeds = seeds_fn()
    except Exception as e:
        raise PluginValidationError(
            f"{prefix}prompt_seeds() raised while validating: {e}"
        ) from e
    if not isinstance(seeds, Sequence):
        raise PluginValidationError(
            f"{prefix}prompt_seeds() must return a sequence, got {type(seeds).__name__!r}"
        )
    for i, seed in enumerate(seeds):
        if not isinstance(seed, PromptSeedDocument):
            raise PluginValidationError(
                f"{prefix}prompt_seeds()[{i}] must be llmops_core.plugins.prompts.PromptSeedDocument, "
                f"got {type(seed).__name__!r}"
            )

    for name in ("on_startup", "on_shutdown"):
        fn = getattr(obj, name, None)
        if not inspect.iscoroutinefunction(fn):
            raise PluginValidationError(
                f"{prefix}{name} must be an async function (async def), "
                f"got {type(fn).__name__!r}"
            )


class AgentRegistry:
    """In-memory registry of validated :class:`AgentPlugin` instances keyed by ``agent_id``."""

    def __init__(self, plugins: Mapping[str, AgentPlugin]) -> None:
        self._plugins: dict[str, AgentPlugin] = dict(plugins)

    @classmethod
    def discover(
        cls,
        *,
        group: str | None = None,
    ) -> AgentRegistry:
        """Load every plugin from ``importlib.metadata`` for the given group.

        Duplicate ``agent_id`` values raise :class:`PluginValidationError` with a clear message.
        """
        g = group or ENTRY_POINT_GROUP
        seen: dict[str, str] = {}
        out: dict[str, AgentPlugin] = {}

        for ep in _entry_points_in_group(g):
            plugin = load_plugin_from_entry_point(ep)
            aid = plugin.agent_id
            if aid in seen:
                raise PluginValidationError(
                    f"Duplicate agent_id {aid!r}: entry point {_label(ep)!r} conflicts with "
                    f"entry point {seen[aid]!r}. Each plugin must use a unique agent_id."
                )
            seen[aid] = _label(ep)
            out[aid] = plugin
            logger.info("Loaded agent plugin %r (%s) from %s", aid, plugin.version, _label(ep))

        return cls(out)

    def get(self, agent_id: str) -> AgentPlugin | None:
        return self._plugins.get(agent_id)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)

    def agent_ids(self) -> Iterator[str]:
        yield from self._plugins.keys()

    def plugins(self) -> Iterator[AgentPlugin]:
        yield from self._plugins.values()

    def items(self) -> Iterator[tuple[str, AgentPlugin]]:
        yield from self._plugins.items()

    def iter_routers(self) -> Iterator[tuple[str, APIRouter]]:
        """Yield ``(agent_id, router)`` for every router returned by each plugin."""
        for plugin in self._plugins.values():
            aid = plugin.agent_id
            for router in plugin.routers():
                yield aid, router

    def iter_prompt_seeds(self) -> Iterator[tuple[str, PromptSeedDocument]]:
        """Yield ``(agent_id, seed)`` for every prompt seed document."""
        for plugin in self._plugins.values():
            aid = plugin.agent_id
            for seed in plugin.prompt_seeds():
                yield aid, seed

    def iter_startup_hooks(self) -> Iterator[tuple[str, AgentStartupHook]]:
        """Yield ``(agent_id, hook)`` for each plugin's ``on_startup`` coroutine function."""
        for plugin in self._plugins.values():
            yield plugin.agent_id, cast(AgentStartupHook, plugin.on_startup)

    def iter_shutdown_hooks(self) -> Iterator[tuple[str, AgentShutdownHook]]:
        """Yield ``(agent_id, hook)`` for each plugin's ``on_shutdown`` coroutine function."""
        for plugin in self._plugins.values():
            yield plugin.agent_id, cast(AgentShutdownHook, plugin.on_shutdown)
