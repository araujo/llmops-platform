# LLMOps Platform

Plugin-based monorepo: a thin **FastAPI host** (`apps/api`), shared **core** library (`packages/core`), and **agent** packages under `packages/agents/`. The host does not implement product-specific behavior; each agent ships its own HTTP surface, prompts, and orchestration behind a stable plugin contract.

For design goals and boundaries, see [docs/architecture_rfc.md](docs/architecture_rfc.md).

## Architecture overview

| Layer | Responsibility |
|-------|------------------|
| **Host (`llmops-api`)** | FastAPI app lifecycle, Mongo-backed prompt repository (when configured), plugin discovery, mounting agent routers. Exposes **operational** routes only (`/`, `/health`, `/metrics`) plus **versioned agent routes** under `/v1/agents/{agent_id}/…`. |
| **Core (`llmops-core`)** | Agent-agnostic types: `AgentPlugin` contract, entry-point registry, prompt storage abstractions, tracing helpers, and storage/connectivity helpers. **No** domain logic or model-provider selection. |
| **Agents (`packages/agents/*`)** | Self-contained packages: FastAPI routers, LangGraph (or other) orchestration, tools, prompts, bootstrap, and package-local data/evals. Registered at runtime via Python entry points. |

There is **no** generic application chat or document API on the host. Capabilities appear only as routes declared by installed agents (for example, the shopping assistant exposes `POST …/chat/shopping` under its own prefix—not a global `/chat`).

## Core vs agents

- **Core** defines *how* plugins are discovered, validated, and wired (protocol, registry, prompt seeding types, shared infrastructure helpers).
- **Agents** define *what* runs (graphs, tools, agent-specific routes and schemas). The host imports agents only indirectly through `importlib.metadata` entry points, not by name in application code.

## Infrastructure services (local / integration)

Typical local development uses Docker Compose ([infrastructure/docker/README.md](infrastructure/docker/README.md)):

| Service | Role in this architecture |
|---------|---------------------------|
| **MongoDB** | Prompt version storage when `LLMOPS_MONGO_URI` is set; host seeds from agent `prompt_seeds()` when enabled. |
| **PostgreSQL + pgvector** | Operational/vector data for agents that choose to use it; **llmops-core** provides pool and pgvector helpers—table design stays in agents. |
| **Langfuse** | Tracing and eval UI; agents use **llmops-core** tracing helpers with environment-driven clients. |
| **LiteLLM (or similar)** | Optional model gateway; point **agent-level** model configuration at it when needed. |

Exact wiring depends on environment variables and each agent’s code paths—not on a single global “RAG platform” API.

## How agent discovery works

1. Each agent package declares one or more entry points in the group **`llmops.agent_plugins`** (see `ENTRY_POINT_GROUP` in **llmops-core**).
2. The host calls `AgentRegistry.discover()`, which loads each entry point, validates that the object satisfies **`AgentPlugin`** (`agent_id`, `version`, `routers()`, `prompt_seeds()`, `on_startup` / `on_shutdown`), and builds an in-memory registry.
3. **Routers** are mounted at **`/v1/agents/{agent_id}`** for each plugin (each `APIRouter` from `routers()` is included with that prefix).
4. **Lifecycle** hooks run with an **`AgentHostContext`** (agent id, logger, `extras` such as prompt registry/repository when available).

If another installed distribution exposes a broken or incompatible entry point, you can set **`LLMOPS_SKIP_PLUGIN_DISCOVERY=1`** to start the host with an empty registry (development/testing only).

## How to add a new agent

1. Create a package under `packages/agents/<your_agent>/` with a `pyproject.toml` that depends on **`llmops-core`**.
2. Implement **`AgentPlugin`** (see [packages/core/README.md](packages/core/README.md)): stable `agent_id`, `routers()` returning `fastapi.APIRouter` instances, `prompt_seeds()`, async `on_startup` / `on_shutdown`.
3. Register an entry point:
   ```toml
   [project.entry-points."llmops.agent_plugins"]
   your_agent = "your_package.plugin:register"
   ```
   where `register()` returns an `AgentPlugin` instance (or a constructible class/factory per registry rules).
4. Add the package as a workspace member in the root **`pyproject.toml`** and run **`uv sync --all-packages`** so the entry point is visible in the same environment as the host.
5. For Docker, extend **`infrastructure/docker/Dockerfile.api`** `COPY` lines to include the new package path (same pattern as `shopping_assistant`).
6. Ensure **`agent_id`** is unique across all installed plugins (duplicates fail discovery).

## Repository layout

| Path | Role |
|------|------|
| `apps/api` | FastAPI host (`llmops-api`) |
| `packages/core` | `llmops-core`: plugins, prompts, tracing/storage helpers |
| `packages/agents/*` | Agent plugins (e.g. `shopping_assistant`) |
| `infrastructure` | Docker Compose and related assets |
| `docs` | Architecture RFC and ADRs |

## Development

Use [uv](https://docs.astral.sh/uv/) from the repo root:

```bash
uv sync --all-packages
```

Run the API:

```bash
uv run --package llmops-api llmops-api
# or: uv run --package llmops-api python -m llmops_api
```

Configure Mongo (and other env) as needed; see `apps/api/llmops_api/settings.py` for **`LLMOPS_*`** variables.

## Testing

From the repo root, install workspace packages plus dev dependencies, then run **pytest**:

```bash
uv sync --all-packages --group dev
uv run pytest
```

Without `uv`: activate a venv with `llmops-api`, `llmops-core`, and `shopping-assistant` installed (editable), install **`pytest`**, then:

```bash
python -m pytest
```

Tests live under **`tests/`** and cover plugin discovery, host HTTP routes, shopping agent mounting, prompt seeding (in-memory repository + optional Mongo), and architecture invariants (no generic `/chat`/`/rag`/… surfaces).

Optional Mongo round-trip (skipped unless `LLMOPS_MONGO_URI` is set):

```bash
LLMOPS_MONGO_URI=mongodb://localhost:27017 uv run pytest -m integration
```

## Docker

From the repo root:

```bash
cp .env.shared.example .env.shared
cp .env.shopping.example .env.shopping
docker compose \
  -f infrastructure/docker/docker-compose.yml \
  --profile shared \
  --profile shopping \
  up --build
```

Env split:

- `.env.shared`: platform-level/runtime-shared settings (`LLMOPS_*`, Langfuse, gateway keys)
- `.env.shopping`: shopping-agent-only provider/model settings (`SHOPPING_ASSISTANT_*`)

Profile split:

- `shared` profile: Mongo, Postgres/pgvector, Redis, Langfuse
- `shopping` profile: API + LiteLLM with the shopping plugin

Details: [infrastructure/docker/README.md](infrastructure/docker/README.md). Catalog and prompt operations for the sample agent use **package-local** CLIs (`shopping-assistant-catalog`, `shopping-assistant-seed-prompts`), not repo-root data directories.

## Further reading

- [packages/core/README.md](packages/core/README.md) — plugin contract, prompts, shared infrastructure responsibilities
- [packages/agents/shopping_assistant/README.md](packages/agents/shopping_assistant/README.md) — reference agent: routes, seeding, data CLIs, evals
