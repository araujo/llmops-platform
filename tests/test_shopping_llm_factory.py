"""Tests for agent-local provider/model selection in shopping assistant."""

from __future__ import annotations

import importlib
from typing import Any

import pytest


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "SHOPPING_ASSISTANT_LLM_PROVIDER",
        "SHOPPING_ASSISTANT_LLM_MODEL",
        "SHOPPING_ASSISTANT_OPENAI_API_KEY",
        "SHOPPING_ASSISTANT_OLLAMA_BASE_URL",
        "SHOPPING_ASSISTANT_ANTHROPIC_API_KEY",
        "SHOPPING_ASSISTANT_LLM_TEMPERATURE",
    ):
        monkeypatch.delenv(key, raising=False)


def _llm_modules() -> tuple[Any, Any]:
    factory_mod = importlib.import_module("shopping_assistant.llm.factory")
    response_mod = importlib.import_module(
        "shopping_assistant.orchestration.response_llm"
    )
    return factory_mod, response_mod


def test_deterministic_mode_when_no_llm_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    _, response_llm = _llm_modules()
    assert response_llm.shopping_chat_model_configured() is False
    out = response_llm.try_generate_llm_reply(
        user_message="hello",
        preferences={},
        search_plan={},
        product_cards=[],
    )
    assert out is None


def test_openai_provider_path_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    factory, _ = _llm_modules()
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("SHOPPING_ASSISTANT_OPENAI_API_KEY", "sk-test")

    calls: dict[str, Any] = {}

    class DummyOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            calls.update(kwargs)

    monkeypatch.setattr(factory, "ChatOpenAI", DummyOpenAI)
    model = factory.create_shopping_chat_model()
    assert isinstance(model, DummyOpenAI)
    assert calls["model"] == "gpt-4o-mini"
    assert calls["api_key"] == "sk-test"


def test_ollama_provider_path_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    factory, _ = _llm_modules()
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_MODEL", "llama3.1:8b")
    monkeypatch.setenv(
        "SHOPPING_ASSISTANT_OLLAMA_BASE_URL",
        "http://localhost:11434",
    )

    calls: dict[str, Any] = {}

    class DummyOllama:
        def __init__(self, **kwargs: Any) -> None:
            calls.update(kwargs)

    monkeypatch.setattr(factory, "ChatOllama", DummyOllama)
    model = factory.create_shopping_chat_model()
    assert isinstance(model, DummyOllama)
    assert calls["model"] == "llama3.1:8b"
    assert calls["base_url"] == "http://localhost:11434"


def test_anthropic_provider_path_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    factory, _ = _llm_modules()
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv(
        "SHOPPING_ASSISTANT_LLM_MODEL",
        "claude-3-5-sonnet-latest",
    )
    monkeypatch.setenv("SHOPPING_ASSISTANT_ANTHROPIC_API_KEY", "ak-test")

    calls: dict[str, Any] = {}

    class DummyAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            calls.update(kwargs)

    monkeypatch.setattr(factory, "ChatAnthropic", DummyAnthropic)
    model = factory.create_shopping_chat_model()
    assert isinstance(model, DummyAnthropic)
    assert calls["model"] == "claude-3-5-sonnet-latest"
    assert calls["api_key"] == "ak-test"


def test_invalid_provider_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_llm_env(monkeypatch)
    factory, _ = _llm_modules()
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_PROVIDER", "foo")
    monkeypatch.setenv("SHOPPING_ASSISTANT_LLM_MODEL", "bar")
    with pytest.raises(
        ValueError,
        match="Unsupported SHOPPING_ASSISTANT_LLM_PROVIDER",
    ):
        factory.create_shopping_chat_model()
