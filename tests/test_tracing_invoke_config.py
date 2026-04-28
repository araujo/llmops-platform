"""Unit tests for Langfuse Runnable config."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from llmops_core.tracing.host import TracingExtras
from llmops_core.tracing.invoke import build_langfuse_llm_invoke_config
from llmops_core.tracing.langfuse import LangfuseClientConfig


class _PluginWithMetadata:
    def build_trace_metadata(self, **kwargs: object) -> dict[str, str]:
        return {"agent_id": "shop", "domain": "shopping"}


def test_build_langfuse_llm_invoke_config_disabled() -> None:
    assert build_langfuse_llm_invoke_config(
        TracingExtras(enabled=False),
        _PluginWithMetadata(),
    ) is None


def test_build_langfuse_llm_invoke_config_no_client() -> None:
    assert build_langfuse_llm_invoke_config(
        TracingExtras(enabled=True, langfuse_config=None),
        _PluginWithMetadata(),
    ) is None


@patch("llmops_core.tracing.invoke.create_langfuse_callback_handler")
def test_build_langfuse_llm_invoke_config_attaches_callback_and_metadata(
    mock_handler: MagicMock,
) -> None:
    mock_handler.return_value = MagicMock(name="handler")
    te = TracingExtras(
        enabled=True,
        langfuse_config=LangfuseClientConfig(
            public_key="pk-test",
            secret_key="sk-test",
            host="http://langfuse:3000",
        ),
    )
    cfg = build_langfuse_llm_invoke_config(
        te,
        _PluginWithMetadata(),
        base_metadata={"request_id": "rid1"},
    )
    assert cfg is not None
    mock_handler.assert_called_once_with(
        public_key="pk-test",
        secret_key="sk-test",
        host="http://langfuse:3000",
        base_url=None,
    )
    assert "callbacks" in cfg
    assert cfg["callbacks"]
    assert cfg["metadata"]["request_id"] == "rid1"
    assert cfg["metadata"]["agent_id"] == "shop"
    assert cfg["metadata"]["domain"] == "shopping"
