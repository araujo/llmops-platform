"""Plugin contract: context, prompts, protocol, lifecycle hook types, registry."""

from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.prompts import PromptSeedDocument
from llmops_core.plugins.protocol import (
    AgentPlugin,
    AgentShutdownHook,
    AgentStartupHook,
)
from llmops_core.plugins.registry import (
    ENTRY_POINT_GROUP,
    AgentRegistry,
    PluginLoadError,
    PluginValidationError,
    coerce_plugin_object,
    load_plugin_from_entry_point,
    validate_plugin,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "AgentHostContext",
    "AgentPlugin",
    "AgentRegistry",
    "AgentShutdownHook",
    "AgentStartupHook",
    "PluginLoadError",
    "PluginValidationError",
    "PromptSeedDocument",
    "coerce_plugin_object",
    "load_plugin_from_entry_point",
    "validate_plugin",
]
