"""Agent-owned chat model factory for shopping assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI


@dataclass(frozen=True, slots=True)
class ShoppingLlmSettings:
    """Agent-local model/provider settings."""

    provider: str
    model: str
    openai_api_key: str | None = None
    ollama_base_url: str | None = None
    anthropic_api_key: str | None = None
    temperature: float = 0.3


def _parse_temperature(raw: str | None) -> float:
    if raw is None or not raw.strip():
        return 0.3
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError("SHOPPING_ASSISTANT_LLM_TEMPERATURE must be numeric") from exc


def read_llm_settings_from_env() -> ShoppingLlmSettings | None:
    """Read agent-scoped LLM settings or return ``None`` when unconfigured."""
    provider = os.environ.get("SHOPPING_ASSISTANT_LLM_PROVIDER", "").strip().lower()
    model = os.environ.get("SHOPPING_ASSISTANT_LLM_MODEL", "").strip()
    if not provider and not model:
        return None
    if not provider or not model:
        raise RuntimeError(
            "Set both SHOPPING_ASSISTANT_LLM_PROVIDER and "
            "SHOPPING_ASSISTANT_LLM_MODEL, or set neither."
        )
    return ShoppingLlmSettings(
        provider=provider,
        model=model,
        openai_api_key=os.environ.get("SHOPPING_ASSISTANT_OPENAI_API_KEY"),
        ollama_base_url=os.environ.get("SHOPPING_ASSISTANT_OLLAMA_BASE_URL"),
        anthropic_api_key=os.environ.get("SHOPPING_ASSISTANT_ANTHROPIC_API_KEY"),
        temperature=_parse_temperature(
            os.environ.get("SHOPPING_ASSISTANT_LLM_TEMPERATURE")
        ),
    )


def create_shopping_chat_model(
    settings: ShoppingLlmSettings | None = None,
) -> BaseChatModel:
    """Create the shopping chat model from agent-scoped env vars.

    Required selector env vars:
    - ``SHOPPING_ASSISTANT_LLM_PROVIDER``: ``openai`` | ``ollama`` | ``anthropic``
    - ``SHOPPING_ASSISTANT_LLM_MODEL``: provider model id
    """
    cfg = settings or read_llm_settings_from_env()
    if cfg is None:
        raise RuntimeError("Shopping LLM is not configured")

    if cfg.provider == "openai":
        if not cfg.openai_api_key:
            raise RuntimeError(
                "Missing SHOPPING_ASSISTANT_OPENAI_API_KEY for provider=openai"
            )
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.openai_api_key,
            temperature=cfg.temperature,
        )

    if cfg.provider == "ollama":
        return ChatOllama(
            model=cfg.model,
            base_url=cfg.ollama_base_url or "http://localhost:11434",
            temperature=cfg.temperature,
        )

    if cfg.provider == "anthropic":
        if not cfg.anthropic_api_key:
            raise RuntimeError(
                "Missing SHOPPING_ASSISTANT_ANTHROPIC_API_KEY for "
                "provider=anthropic"
            )
        return ChatAnthropic(
            model=cfg.model,
            api_key=cfg.anthropic_api_key,
            temperature=cfg.temperature,
        )

    raise ValueError(
        f"Unsupported SHOPPING_ASSISTANT_LLM_PROVIDER={cfg.provider!r}; "
        "supported: openai, ollama, anthropic"
    )
