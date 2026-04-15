"""Generic storage settings (no table or agent names)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    """Connection pool settings for PostgreSQL (dsn + pool bounds)."""

    dsn: str
    """``psycopg`` connection string (URI or key=value)."""

    pool_min_size: int = 1
    pool_max_size: int = 10
    connect_timeout_s: float = 30.0
    """Passed through to ``psycopg.connect`` as ``connect_timeout`` (seconds)."""

    @classmethod
    def from_env(
        cls,
        *,
        dsn_env: str = "LLMOPS_POSTGRES_DSN",
        prefix: str = "",
    ) -> PostgresSettings | None:
        """Load DSN from ``{prefix}{dsn_env}``; return ``None`` if unset or empty."""
        key = f"{prefix}{dsn_env}" if prefix else dsn_env
        raw = os.environ.get(key)
        if not raw or not raw.strip():
            return None
        return cls(dsn=raw.strip())


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Bundle of optional storage backends for the host process."""

    postgres: PostgresSettings | None = None
