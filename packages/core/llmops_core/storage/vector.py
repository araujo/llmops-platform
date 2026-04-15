"""pgvector helpers: types and extension bootstrap (no application tables)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import psycopg


def register_vector_types(conn: psycopg.Connection[Any]) -> None:
    """Register pgvector adapters on a :class:`psycopg.Connection` (call once per conn)."""
    from pgvector.psycopg import register_vector

    register_vector(conn)


def ensure_pgvector_extension(conn: psycopg.Connection[Any]) -> None:
    """Run ``CREATE EXTENSION IF NOT EXISTS vector`` (requires sufficient DB privileges).

    Prefer running extensions in infra/migrations; this is a convenience for dev/tests.
    """
    prev = conn.autocommit
    conn.autocommit = True
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        conn.autocommit = prev


def vector_param(embedding: Sequence[float]) -> Any:
    """Wrap a float sequence for parameterized inserts/updates (pgvector ``Vector``)."""
    from pgvector.psycopg import Vector

    return Vector(embedding)


def assert_embedding_dim(embedding: Sequence[float], *, dim: int) -> None:
    """Validate embedding length for a fixed schema dimension (generic guard)."""
    if len(embedding) != dim:
        msg = f"expected embedding dim {dim}, got {len(embedding)}"
        raise ValueError(msg)
