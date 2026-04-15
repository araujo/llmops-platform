# llmops-core

Shared, **agent-agnostic** library for the LLMOps host and agent packages. It defines the plugin contract, discovery/registry, prompt abstractions, tracing helpers, and PostgreSQL/pgvector utilities—without embedding any single product’s business logic or model-provider decisions.

**Boundary:** keep domain rules, agent-specific tools, and database schemas inside agent packages. Use **llmops-core** for types, loaders, and reusable infrastructure helpers only.

---

## Plugin contract

The host depends on the structural protocol **`AgentPlugin`** (`llmops_core.plugins.protocol`):

| Member | Purpose |
|--------|---------|
| **`agent_id`** | Non-empty string slug; used in URLs and namespacing (`/v1/agents/{agent_id}/…`). Must be unique across discovered plugins. |
| **`version`** | Plugin version string (e.g. package version) for logs and diagnostics. |
| **`routers()`** | Returns a sequence of **`fastapi.APIRouter`** instances; the host mounts them under each plugin’s prefix. |
| **`prompt_seeds()`** | Returns **`PromptSeedDocument`** instances the host may upsert into the prompt store on startup (if seeding is enabled). |
| **`on_startup` / `on_shutdown`** | Async hooks receiving **`AgentHostContext`** (see below). |

**`AgentHostContext`** (`llmops_core.plugins.context`) exposes `agent_id`, `logger`, and **`extras`**: an opaque mapping the host can populate (for example `prompt_registry`, `prompt_repository`, `settings`). Agents should not assume keys exist unless documented for their deployment.

Implementations live in agent packages; the host must not import agent modules by name—only load them via entry points.

---

## Registry and discovery

- **Entry-point group:** **`llmops.agent_plugins`** (constant **`ENTRY_POINT_GROUP`**).
- **`AgentRegistry.discover()`** loads every entry point in that group via **`importlib.metadata`**, validates each plugin (**`validate_plugin`**), and rejects duplicate **`agent_id`** values.
- Helpers such as **`load_plugin_from_entry_point`** and **`coerce_plugin_object`** support tests and tooling; entry points may resolve to a class (no-arg constructible), a factory callable, or an instance.

The FastAPI host uses this registry to run lifecycle hooks and to mount routers (see `apps/api/llmops_api/lifecycle.py`).

---

## Prompts

Core provides:

- **`PromptSeedDocument`** — seed payload for initial prompt rows (aligned with repository models).
- **`MongoPromptRepository`** — MongoDB implementation of **`PromptRepository`** (collections, indexes, upserts).
- **`PromptRegistry`** — in-process cache/registry over repository reads (invalidated when the host seeds on startup).
- **`seed_prompts_from_seeds`** — applies seeds for a given `agent_id` when the host boots (if `LLMOPS_SEED_PROMPTS_ON_STARTUP` and Mongo are configured).

Agents supply seeds through **`AgentPlugin.prompt_seeds()`**; they do not talk to MongoDB through ad hoc globals—the host owns the client and repository wiring.

---

## Shared infrastructure responsibilities

These modules are **optional** for agents: use them when you need consistent configuration patterns.

| Area | Package path | Responsibility |
|------|----------------|----------------|
| **Tracing** | `llmops_core.tracing` | Langfuse-oriented helpers (callbacks, runnable config) for LangChain runs. |
| **Storage** | `llmops_core.storage` | Postgres connection pooling, pgvector extension/helpers, embedding dimension checks, **`StorageBundle`** lifecycle. **Does not** define agent-specific tables—agents own SQL and migrations in their own packages. |

Mongo prompt storage is part of **`llmops_core.prompts`**, not `storage`, by design.

---

## Public exports

The package root (`llmops_core.__init__`) re-exports the main plugin and prompt symbols plus tracing and storage helpers for convenience. Prefer submodule imports in large codebases if you want tighter dependency boundaries.

---

## See also

- [Root README](../../README.md) — architecture, discovery, adding an agent
- [docs/architecture_rfc.md](../../docs/architecture_rfc.md) — full RFC
