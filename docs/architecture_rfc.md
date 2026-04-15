# Architecture RFC: Plugin-Based LLMOps Platform

**Status:** Draft  
**Audience:** Implementers  

## 1. Goals

- Provide a **thin, agent-agnostic host** that wires HTTP, observability, and persistence—never product-specific agent logic.
- Ship **self-contained agent packages** (code + metadata + optional assets) that register at runtime via a stable contract.
- Allow **adding agents without editing host business logic** (only configuration and dependency wiring, if needed).
- Standardize on **FastAPI** (shell), **LangChain** + **LangGraph** (orchestration inside agents), **Langfuse** (tracing/evals), **MongoDB** (prompt registry/versioning), **PostgreSQL + pgvector** (relational + vector data).
- Bootstrap with **`shopping_assistant`** as the first agent package to validate the contract end-to-end.
- Support a **Docker-based local environment** that mirrors integration points (not necessarily full production parity).

## 2. Non-goals

- Production hardening (HA, multi-tenant authz models, full CI/CD) in the first iteration.
- A generic “no-code” agent builder UI.
- Mandating a single LLM provider; agents may choose providers via configuration.
- Duplicating Langfuse’s trace storage in app DBs except where needed for correlation IDs.

## 3. Architectural Principles

| Principle | Implication |
|-----------|-------------|
| **Host is dumb about agents** | Host exposes transport, discovery, shared infra clients, and plugin loading—no imports of agent-specific modules in host “business” code paths. |
| **Agents own their graphs** | LangGraph graphs, tools, and LangChain chains live inside agent packages; host calls a narrow entry API. |
| **Configuration over code changes** | New agents appear via package install + env/config registration, not host patches. |
| **Observable by default** | All agent runs emit Langfuse traces (and optional scores); correlation from HTTP request → trace is preserved. |
| **Clear data boundaries** | MongoDB holds prompt artifacts and versions; Postgres holds operational/domain tables and vectors; agents declare what they read/write. |

## 4. Directory Structure (Proposed)

```text
llmops-platform/
├── docker/
│   ├── compose.yaml          # API, MongoDB, Postgres (+ pgvector), Langfuse deps as needed
│   └── ...
├── src/
│   └── llmops_host/          # Installable host package
│       ├── main.py           # FastAPI app factory
│       ├── api/              # Routers: health, agent invoke, admin (prompt sync hooks if any)
│       ├── plugins/          # Loader, registry, contract types only
│       ├── integrations/     # Langfuse client, Mongo prompt store, Postgres pool, optional thin facades
│       └── settings.py
├── agents/
│   └── shopping_assistant/   # First agent: own pyproject or namespace package
│       ├── pyproject.toml
│       └── shopping_assistant/
│           ├── __init__.py   # Exports plugin entry (register)
│           ├── graph.py      # LangGraph
│           ├── tools.py
│           └── manifest.yaml # id, version, routes, required secrets keys (optional)
├── docs/
│   └── architecture_rfc.md
└── pyproject.toml            # Workspace root (optional uv/poetry)
```

Optional: publish agents as separate distributions; host depends on them as optional extras or installs them in the Docker image via `pip install -e agents/shopping_assistant`.

## 5. Plugin Contract

**Discovery:** Each agent package exposes a single registration function (e.g. `register_plugin(registry: AgentRegistry) -> None`) or a setuptools entry point (`llmops.agents = shopping_assistant:register`).

**Identity:** Stable `agent_id` (slug), semver or build metadata, human-readable name.

**HTTP surface (host-owned):** Host maps URLs like `POST /v1/agents/{agent_id}/invoke` (and optional `GET /v1/agents` for listing). Agents do **not** register arbitrary FastAPI routers in v1; they return structured results/errors through the contract to keep the surface uniform and auditable.

**Invocation API (conceptual):**

```python
class AgentPlugin(Protocol):
    agent_id: str
    async def invoke(self, payload: InvokeRequest, ctx: InvokeContext) -> InvokeResponse: ...
```

- **`InvokeRequest`:** user message, session/thread id, optional JSON attachments, feature flags.
- **`InvokeContext`:** logger, Langfuse trace/span handles (or callback handler), Mongo prompt resolver interface, DB session factories **scoped by agent** (see data ownership), secrets/config snapshot.
- **`InvokeResponse`:** assistant message, structured tool outputs, token usage metadata for Langfuse.

**Lifecycle:** Optional `async def healthcheck(ctx) -> bool` for readiness probes per agent.

**Failure:** Agents raise typed errors; host maps them to HTTP and Langfuse error events.

## 6. Startup Flow

1. Load **settings** (env): DB URLs, Langfuse keys, plugin list or entry-point scan.
2. Initialize **MongoDB** client (prompt store), **Postgres** pool (with vector extension assumed), **Langfuse** client/callback factory.
3. **Discover plugins** via entry points or explicit module paths from config.
4. **Register** each plugin in an in-memory `AgentRegistry` keyed by `agent_id`; fail fast on duplicate IDs.
5. Build **FastAPI** app: mount global middleware (request ID, CORS), register generic routers that delegate to `registry.get(agent_id).invoke`.
6. **Optional:** background task to sync prompt definitions from repo/Git to Mongo (if using file-backed prompts)—out of band from request path.

## 7. Prompt Storage & Versioning Strategy

**Store:** MongoDB collections (names illustrative):

- `prompts` — logical prompt key (`agent_id`, `name`), current pointer to active version, tags.
- `prompt_versions` — immutable documents: `version` (int or semver), `template` (Jinja or f-string metadata), `model_defaults`, `created_at`, `created_by`, `labels` (e.g. `production`, `canary`).

**Resolution:** At invoke time, agent code requests `(agent_id, prompt_name, label|version)` via a small **host-provided resolver** that reads Mongo; cache with TTL in the host process.

**Authoring flow:** Prompts can be seeded via migration scripts or admin API; Langfuse can reference the same `prompt_name` + version in trace metadata for cross-system alignment.

**Versioning rules:** New content → new `prompt_versions` document; switching “active” is an atomic pointer update on `prompts` or label move—no in-place edits for production labels.

## 8. Data Ownership Rules

| Store | Owns | Agents may… |
|-------|------|-------------|
| **MongoDB** | Prompt templates, version history, prompt metadata | Read via resolver; write only through dedicated admin/sync paths (not ad hoc in invoke unless explicitly allowed). |
| **PostgreSQL** | Sessions, users, agent-specific tables **namespaced** (e.g. schema per agent or `agent_id` column + RLS later) | Receive scoped repositories/sessions in `InvokeContext` for their namespace only. |
| **pgvector** | Embeddings tied to agent-owned entities | Same as Postgres; vector dims and indexes declared per agent migration. |
| **Langfuse** | Traces, scores, datasets | Write via callbacks; read for eval pipelines outside the hot path (optional). |

The host **does not** infer cross-agent joins; shared analytics are batch jobs reading with explicit contracts.

## 9. How to Add a New Agent

1. **Create package** under `agents/<agent_id>/` with `register` entry point and LangGraph/LangChain implementation.
2. **Declare** `agent_id` and metadata in `manifest.yaml` (optional but recommended).
3. **Add dependency** to the host image or workspace (e.g. optional extra `pip install llmops-host[agents-myagent]`).
4. **Register** in config: `PLUGINS=myagent` or enable entry-point discovery.
5. **Provision data:** Mongo prompt seed scripts; Postgres migrations for that agent’s tables/schema.
6. **Configure** Langfuse project/env variables if separated per agent.
7. **Verify** via `GET /v1/agents` and `POST /v1/agents/{agent_id}/invoke` against Docker Compose.

No edits to host Python modules are required except **dependency lists** (lockfile / Docker image) and **configuration**—consistent with “no host business logic changes.”

## 10. Open Points (Next Implementation Pass)

- Exact entry-point naming and `pyproject` metadata.
- Whether v1 allows agents to contribute optional sub-routers under `/v1/agents/{id}/...` for streaming/SSE.
- Langfuse multi-project vs single-project with `agent_id` tags.

---

*This RFC is intentionally concise; implementation should add ADRs only when deviating from the above.*
