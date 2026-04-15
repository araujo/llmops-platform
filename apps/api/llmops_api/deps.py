"""FastAPI dependencies for shared host services (no business logic)."""

from __future__ import annotations

from fastapi import Request

from llmops_api.settings import Settings
from llmops_core.plugins.registry import AgentRegistry
from llmops_core.prompts import PromptRegistry, PromptRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_agent_registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry


def get_prompt_registry(request: Request) -> PromptRegistry | None:
    return request.app.state.prompt_registry


def get_prompt_repository(request: Request) -> PromptRepository | None:
    return request.app.state.prompt_repository
