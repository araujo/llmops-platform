# LLMOps Platform

Plugin-based monorepo for building **agent-agnostic LLMOps systems**.

This project is intentionally designed so that the platform remains operational even if the first agent is removed.

**Agents are products.**
**The platform is the system.**

The goal is not to build a great architecture for one agent.
The goal is to build a reusable platform for many independent agents.

The host does not implement product-specific behavior. Each agent ships its own HTTP surface, prompts, orchestration, evaluations, and model-provider choices behind a stable plugin contract.

For design goals, architecture decisions, diagrams, and boundaries, see:

→ `docs/architecture_rfc.md`

---

## Core Architectural Principle

**The platform must survive even if the first agent disappears.**

This means:

* no shopping-specific logic inside the host
* no global `/chat`, `/rag`, or generic application endpoints
* no platform-level model/provider ownership
* no prompt logic coupled to one use case
* no tracing or evaluation logic implemented only for one agent

Everything reusable belongs to the platform.
Everything domain-specific belongs to the agent.

---

## Architecture Overview

| Layer                            | Responsibility                                                                                                                                                                                                                               |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Host (`llmops-api`)**          | FastAPI app lifecycle, Mongo-backed prompt repository (when configured), plugin discovery, mounting agent routers. Exposes only operational routes (`/`, `/health`, `/metrics`) plus versioned agent routes under `/v1/agents/{agent_id}/…`. |
| **Core (`llmops-core`)**         | Agent-agnostic types: `AgentPlugin` contract, entry-point registry, prompt storage abstractions, tracing helpers, evaluation execution patterns, and storage/connectivity helpers. No domain logic and no model-provider selection.          |
| **Agents (`packages/agents/*`)** | Self-contained packages: FastAPI routers, LangGraph (or other) orchestration, tools, prompts, datasets, evals, bootstrap, and package-local data. Registered at runtime via Python entry points.                                             |

There is **no** generic application chat or document API on the host.

Capabilities appear only as routes declared by installed agents.

Example:

```text
POST /v1/agents/shopping_assistant/chat/shopping
```

—not a global:

```text
POST /chat
```

---

## Core vs Agents

### Core defines HOW

Core defines how plugins are discovered, validated, traced, evaluated, and wired:

* plugin protocol
* registry
* prompt repository abstractions
* tracing hooks
* evaluation execution pattern
* storage helpers
* lifecycle contracts

### Agents define WHAT

Agents define what actually runs:

* graphs
* tools
* prompts
* datasets
* business rules
* retrieval logic
* provider/model configuration
* agent-specific routes and schemas

The host imports agents only indirectly through Python entry points (`importlib.metadata`), never by hardcoded package imports.

---

## Reference Agent

The project includes a `shopping_assistant` package as the first reference implementation.

It is used to validate the platform architecture:

* prompt management and versioning
* tracing and observability with Langfuse
* evaluation datasets and execution
* provider flexibility (Ollama, OpenAI, etc.)
* plugin discovery
* isolated deployment

It helps users search products by:

* product type
* brand
* attributes
* price

combining deterministic retrieval with optional LLM-generated responses.

### Important

`shopping_assistant` is **not** the platform.

It is a reference implementation.

If the package is removed, the platform should still work correctly.

That is the architectural standard.

---

## Infrastructure Services (Local / Integration)

Typical local development uses Docker Compose (`infrastructure/docker/README.md`):

| Service                   | Role in this architecture                                                                                                                |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **MongoDB**               | Prompt version storage when `LLMOPS_MONGO_URI` is set; host seeds from agent `prompt_seeds()` when enabled.                              |
| **PostgreSQL + pgvector** | Operational/vector data for agents that choose to use it; `llmops-core` provides pool and pgvector helpers—table design stays in agents. |
| **Langfuse**              | Tracing and evaluation UI; agents use `llmops-core` tracing helpers with environment-driven clients.                                     |
| **LiteLLM (or similar)**  | Optional model gateway; point **agent-level** model configuration at it when needed.                                                     |

Exact wiring depends on environment variables and each agent’s code paths—not on a single global “RAG platform” API.

---

## Provider Ownership

**Model/provider ownership belongs to the agent, not the platform.**

This means:

* one agent can use Ollama + Llama locally
* another can use OpenAI
* another can use Anthropic

without changing the core architecture.

The platform should never force a global provider decision.

---

## Tracing and Evaluation

Tracing and evaluation are **infrastructure capabilities**, not shopping-specific features.

### Tracing

Agents use shared tracing helpers from `llmops-core` and can emit spans to Langfuse using environment-driven configuration.

### Evaluation

Evaluation is not a host concern.

Each agent owns:

* its datasets
* expected outputs
* assertions
* quality rules

Core only provides the execution pattern.

This keeps evaluation reusable without centralizing business logic.

---

## How Agent Discovery Works

1. Each agent package declares one or more entry points in the group `llmops.agent_plugins`.
2. The host calls `AgentRegistry.discover()`.
3. Each entry point is loaded and validated against the `AgentPlugin` contract.
4. Routers are mounted automatically under `/v1/agents/{agent_id}`.
5. Lifecycle hooks run with an `AgentHostContext`.

Required plugin behaviors:

* stable `agent_id`
* `version`
* `routers()`
* `prompt_seeds()`
* async `on_startup()`
* async `on_shutdown()`

If another installed distribution exposes a broken entry point, use:

```bash
LLMOPS_SKIP_PLUGIN_DISCOVERY=1
```

for development/testing only.

---

## How to Add a New Agent

### Required

1. Create a package under:

```text
packages/agents/<your_agent>/
```

2. Add a `pyproject.toml` depending on `llmops-core`

3. Implement `AgentPlugin`

4. Register the entry point:

```toml
[project.entry-points."llmops.agent_plugins"]
your_agent = "your_package.plugin:register"
```

5. Add the package as a workspace member in root `pyproject.toml`

6. Run:

```bash
uv sync --all-packages
```

7. Extend Docker image copy paths in:

```text
infrastructure/docker/Dockerfile.api
```

8. Ensure `agent_id` is unique

---

## What You Should NOT Change

Adding a new agent should **not** require changing:

* `apps/api/main.py`
* plugin registry behavior
* tracing infrastructure
* prompt repository implementation
* host lifecycle design
* shared platform abstractions

If a new agent requires changing platform internals, the architecture is being violated.

The goal is plug-in, not patch-in.

---

## Repository Layout

| Path                | Role                                                         |
| ------------------- | ------------------------------------------------------------ |
| `apps/api`          | FastAPI host (`llmops-api`)                                  |
| `packages/core`     | `llmops-core`: plugins, prompts, tracing, evaluation helpers |
| `packages/agents/*` | Agent plugins (example: `shopping_assistant`)                |
| `infrastructure`    | Docker Compose and runtime assets                            |
| `docs`              | Architecture RFC and ADRs                                    |

---

## Development

Use `uv` from the repo root:

```bash
uv sync --all-packages
```

Run the API:

```bash
uv run --package llmops-api llmops-api
```

or:

```bash
uv run --package llmops-api python -m llmops_api
```

Configure Mongo and other environment variables as needed.

See:

```text
apps/api/llmops_api/settings.py
```

for `LLMOPS_*` variables.

---

## Testing

Install workspace packages plus dev dependencies:

```bash
uv sync --all-packages --group dev
uv run pytest
```

Tests cover:

* plugin discovery
* host HTTP routes
* shopping agent mounting
* prompt seeding
* Mongo integration
* architecture invariants
* no generic `/chat` / `/rag` surfaces

Optional Mongo round-trip:

```bash
LLMOPS_MONGO_URI=mongodb://localhost:27017 uv run pytest -m integration
```

---

## Docker

From repo root:

```bash
cp .env.shared.example .env.shared
cp .env.shopping.example .env.shopping

docker compose \
  -f infrastructure/docker/docker-compose.yml \
  --profile shared \
  --profile shopping \
  up --build
```

### Env split

* `.env.shared` → platform-level/runtime-shared settings (`LLMOPS_*`, Langfuse, gateway keys)
* `.env.shopping` → shopping-agent-only provider/model settings (`SHOPPING_ASSISTANT_*`)

### Profile split

* `shared` → Mongo, Postgres/pgvector, Redis, Langfuse
* `shopping` → API + LiteLLM + shopping plugin

Catalog and prompt operations use package-local CLIs:

* `shopping-assistant-catalog`
* `shopping-assistant-seed-prompts`

—not repo-root data directories.

---

## Further Reading

- [packages/core/README.md](packages/core/README.md) — plugin contract, prompts, shared infrastructure responsibilities
- [packages/agents/shopping_assistant/README.md](packages/agents/shopping_assistant/README.md) — reference agent: routes, seeding, data CLIs, evals
- [doc/architecture-rfc.md](doc/architecture-rfc.md) — RFC Architecture
