"""Host configuration from environment (no agent-specific defaults)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API process settings. Env vars use prefix ``LLMOPS_`` (see fields)."""

    model_config = SettingsConfigDict(
        env_prefix="LLMOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "llmops-api"
    mongo_uri: str | None = None
    mongo_database: str = "llmops"
    mongo_prompt_collection: str = "llmops_prompt_versions"
    seed_prompts_on_startup: bool = True
    skip_plugin_discovery: bool = False
    """If true, skip entry-point discovery (empty :class:`AgentRegistry`). For tests/dev."""
