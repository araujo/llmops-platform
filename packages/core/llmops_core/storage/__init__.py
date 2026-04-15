"""Shared database connectivity (Postgres + pgvector helpers). No agent schemas here.

**Boundary**

- **Core (this package):** connection pools, pgvector registration/extension helper,
  embedding dimension guards, and lifecycle bundles for the host.
- **Agents:** own tables, indexes, migrations, and queries. They receive a pool (or DSN)
  via host ``extras`` and apply SQL in their packages—never in ``llmops_core.storage``.
"""

from llmops_core.storage.config import PostgresSettings, StorageSettings
from llmops_core.storage.lifecycle import (
    StorageBundle,
    close_storage,
    open_storage,
    storage_extras,
)
from llmops_core.storage.postgres import PostgresPoolManager
from llmops_core.storage.vector import (
    assert_embedding_dim,
    ensure_pgvector_extension,
    register_vector_types,
    vector_param,
)

__all__ = [
    "PostgresPoolManager",
    "PostgresSettings",
    "StorageBundle",
    "StorageSettings",
    "assert_embedding_dim",
    "close_storage",
    "ensure_pgvector_extension",
    "open_storage",
    "register_vector_types",
    "storage_extras",
    "vector_param",
]
