"""Generic PostgreSQL connection pool (no schema or migrations)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from llmops_core.storage.config import PostgresSettings


class PostgresPoolManager:
    """Owns a :class:`psycopg_pool.ConnectionPool` lifecycle (open/close).

    Table creation, migrations, and row logic belong to agents or app layers—core
    only provides connectivity.
    """

    def __init__(self, settings: PostgresSettings) -> None:
        self._settings = settings
        self._pool: ConnectionPool | None = None

    @property
    def settings(self) -> PostgresSettings:
        return self._settings

    @property
    def pool(self) -> ConnectionPool:
        if self._pool is None:
            raise RuntimeError("Postgres pool is not open; call open() first.")
        return self._pool

    def open(self) -> None:
        """Create and open the pool (idempotent if already open)."""
        if self._pool is not None:
            return
        s = self._settings
        self._pool = ConnectionPool(
            s.dsn,
            min_size=s.pool_min_size,
            max_size=s.pool_max_size,
            kwargs={"connect_timeout": int(s.connect_timeout_s)},
            open=True,
        )

    def close(self, *, timeout: float = 30.0) -> None:
        """Close the pool and release connections."""
        if self._pool is None:
            return
        self._pool.close(timeout=timeout)
        self._pool = None

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        """Borrow a connection from the pool (context manager)."""
        with self.pool.connection() as conn:
            yield conn
