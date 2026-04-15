# shopping-assistant

Self-contained **shopping assistant** agent plugin: the first reference implementation of **`AgentPlugin`**. Shopping-specific HTTP handlers, prompts, orchestration scaffolding, and package-local data/evals live here—not in **`llmops-core`** or **`apps/api`**.

There is no separate global “platform” chat API; this agent is reached only under the host’s agent prefix (see [Routes](#routes)).

---

## What the agent does

- Exposes a small HTTP surface for metadata and a single chat-style turn for development and integration tests.
- Runs a **LangGraph** pipeline (`orchestration/graph.py`) for `run_shopping_turn`; when no agent LLM provider/model is configured, responses stay deterministic.
- Ships **prompt seeds** for MongoDB via **`PromptSeedDocument`**; the host can seed them on startup, or you can run the package CLI against Mongo manually.

Heavy product logic (retrieval, catalog-backed answers, production guardrails) is expected to evolve under `domain/`, `orchestration/`, and `tools/` without changing the host.

---

## Routes

The host mounts this package’s router at:

**`/v1/agents/shopping_assistant`**

| Method | Path (after prefix) | Description |
|--------|---------------------|-------------|
| **GET** | `/info` | Returns `agent_id` (`shopping_assistant`) and package version. |
| **POST** | `/chat/shopping` | Accepts a chat message JSON body and returns a deterministic or LLM-grounded reply from the shopping orchestration pipeline. |

Example (local host on port 8000):

- `GET http://localhost:8000/v1/agents/shopping_assistant/info`
- `POST http://localhost:8000/v1/agents/shopping_assistant/chat/shopping`

The host does not expose a generic **`/chat`** or **`/documents`** route; only these agent-scoped paths exist for this plugin.

---

## Plugin registration and entry point

```toml
[project.entry-points."llmops.agent_plugins"]
shopping_assistant = "shopping_assistant.plugin:register"
```

`shopping_assistant.plugin:register` returns an **`AgentPlugin`** instance (`ShoppingAssistantPlugin`) that wires routers, prompt seeds, and lifecycle delegates.

---

## Prompt seeding

**Host-driven (recommended when Mongo is configured):** With **`LLMOPS_MONGO_URI`** set and **`LLMOPS_SEED_PROMPTS_ON_STARTUP`** true (default in `Settings`), the API process loads seeds from **`prompt_seeds()`** and upserts them for `shopping_assistant`.

**Manual / CI:** Console script **`shopping-assistant-seed-prompts`** (see `[project.scripts]`):

```bash
uv run --package shopping-assistant shopping-assistant-seed-prompts --mongo-uri "mongodb://localhost:27017"
```

Uses the same collection/database conventions as the host (`LLMOPS_MONGO_DATABASE`, `LLMOPS_MONGO_PROMPT_COLLECTION` or flags on the CLI). Implementation: `bootstrap/seed_prompts.py` and `bootstrap/cli.py`.

Prompt templates and catalog metadata live under **`shopping_assistant/prompts/`** (including packaged documents where applicable).

---

## Agent-local LLM configuration

Model/provider ownership is fully local to this package (`shopping_assistant/llm/factory.py`).
No host/core provider logic is required.

### OpenAI

```bash
export SHOPPING_ASSISTANT_LLM_PROVIDER=openai
export SHOPPING_ASSISTANT_LLM_MODEL=gpt-4o-mini
export SHOPPING_ASSISTANT_OPENAI_API_KEY=sk-...
```

### Ollama

```bash
export SHOPPING_ASSISTANT_LLM_PROVIDER=ollama
export SHOPPING_ASSISTANT_LLM_MODEL=llama3.1:8b
export SHOPPING_ASSISTANT_OLLAMA_BASE_URL=http://localhost:11434
```

### Anthropic

```bash
export SHOPPING_ASSISTANT_LLM_PROVIDER=anthropic
export SHOPPING_ASSISTANT_LLM_MODEL=claude-3-5-sonnet-latest
export SHOPPING_ASSISTANT_ANTHROPIC_API_KEY=...
```

Optional:

```bash
export SHOPPING_ASSISTANT_LLM_TEMPERATURE=0.3
```

If provider/model is unset (or LLM invocation fails), the agent falls back to deterministic mode.

---

## Package layout

| Path | Responsibility |
|------|----------------|
| `shopping_assistant/plugin.py` | **`register()`** and **`AgentPlugin`** implementation |
| `shopping_assistant/app/` | HTTP routers (`router.py`), request/response schemas |
| `shopping_assistant/domain/` | Domain types and rules (pure Python) |
| `shopping_assistant/orchestration/` | LangGraph graph and state (`graph.py`, `state.py`) |
| `shopping_assistant/prompts/` | Seeds, naming, packaged prompt documents |
| `shopping_assistant/bootstrap/` | Seed helpers, lifecycle hooks, **`shopping-assistant-seed-prompts`** CLI |
| `shopping_assistant/cli/` | **`shopping-assistant-catalog`** CLI |
| `shopping_assistant/data/` | Package-local `raw/`, `enriched/`, `samples/` (no repo-root coupling) |
| `shopping_assistant/evals/` | Eval harness placeholder and `datasets/` |
| `shopping_assistant/paths.py` | Canonical paths under the package tree only |

---

## Data paths and catalog CLI

All filesystem paths resolve **inside** the `shopping_assistant` package via **`paths.py`** (`data_raw_dir()`, `data_enriched_dir()`, `evals_datasets_dir()`, etc.)—not relative to the repository root.

**`shopping-assistant-catalog`** subcommands:

| Subcommand | Purpose |
|------------|---------|
| `download` | Scaffold for fetching raw catalog assets into `data/raw/` |
| `enrich` | Scaffold for raw → `data/enriched/` |
| `load` | Placeholder for loading enriched data into runtime stores |

```bash
uv run --package shopping-assistant shopping-assistant-catalog download
```

Run from a checkout where the package is installed; data directories are created under the package as needed (`ensure_operational_dirs()`).

---

## Eval and testing flow

- **Datasets:** Place files under **`shopping_assistant/evals/datasets/`** (package-local). Helpers list them via `evals.runner.list_local_datasets()`.
- **Runner:** `evals.runner.run_eval_suite` is a **placeholder** (`NotImplementedError`) intended to be wired to your eval harness or CI.
- **API tests:** Hit **`/v1/agents/shopping_assistant/info`** and **`/chat/shopping`** against a running `llmops-api` with this package installed and discovery enabled.

---

## Status

Plugin wiring, routes, prompt seeding, and LangGraph skeleton are in place; deeper shopping behavior belongs in this package’s `domain/`, `orchestration/`, and `tools/` as you iterate.

---

## See also

- [Root README](../../../README.md) — platform architecture and adding agents
- [llmops-core README](../../core/README.md) — plugin contract and shared modules
