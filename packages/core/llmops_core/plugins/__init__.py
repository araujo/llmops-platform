"""Plugin contract: context, prompts, protocol, base class, registry."""

from llmops_core.plugins.base import BaseAgentPlugin
from llmops_core.plugins.evals import AgentEvalRunner
from llmops_core.plugins.context import AgentHostContext
from llmops_core.plugins.infra import (
    APP_STATE_ATTR_TRACING_EXTRAS,
    EXTRA_KEY_EVAL_RUNNER,
    EXTRA_KEY_TRACING,
    merge_agent_trace_metadata,
)
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
    "AgentEvalRunner",
    "AgentHostContext",
    "AgentPlugin",
    "AgentRegistry",
    "AgentShutdownHook",
    "AgentStartupHook",
    "APP_STATE_ATTR_TRACING_EXTRAS",
    "BaseAgentPlugin",
    "EXTRA_KEY_EVAL_RUNNER",
    "EXTRA_KEY_TRACING",
    "PluginLoadError",
    "PluginValidationError",
    "PromptSeedDocument",
    "coerce_plugin_object",
    "load_plugin_from_entry_point",
    "merge_agent_trace_metadata",
    "validate_plugin",
]
