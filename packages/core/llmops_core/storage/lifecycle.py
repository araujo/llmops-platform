"""Open/close helpers for :class:`~llmops_core.storage.config.StorageSettings`."""

from __future__ import annotations

from dataclasses import dataclass

from llmops_core.storage.config import StorageSettings
from llmops_core.storage.postgres import PostgresPoolManager


@dataclass
class StorageBundle:
    """Opened storage clients for ``app.state`` (or similar) in the API host."""

    postgres: PostgresPoolManager | None = None


def open_storage(settings: StorageSettings) -> StorageBundle:
    """Open configured backends. Omitted backends stay ``None``."""
    pg: PostgresPoolManager | None = None
    if settings.postgres is not None:
        pg = PostgresPoolManager(settings.postgres)
        pg.open()
    return StorageBundle(postgres=pg)


def close_storage(bundle: StorageBundle, *, pool_close_timeout: float = 30.0) -> None:
    """Close all backends in a bundle (safe if partially opened)."""
    if bundle.postgres is not None:
        bundle.postgres.close(timeout=pool_close_timeout)


def storage_extras(bundle: StorageBundle) -> dict[str, object]:
    """Suggested keys for ``AgentHostContext.extras`` (host merges with other services).

    Agents may use ``postgres_pool`` for their own SQL; core defines no tables.
    """
    out: dict[str, object] = {}
    if bundle.postgres is not None:
        out["postgres_pool"] = bundle.postgres
    return out
