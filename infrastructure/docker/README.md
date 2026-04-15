# Docker (local stack)

Compose file: `docker-compose.yml` in this directory.

## Runtime env strategy

Runtime env is split at the repository root:

- `.env.shared`: platform-level config (host infra, Langfuse, LiteLLM/gateway keys).
- `.env.shopping`: shopping-agent config only (provider/model/API keys for `shopping_assistant`).

The compose file loads them directly in the `api` service (`.env.shared` then `.env.shopping`), so shopping-specific provider/model decisions stay agent-owned.

Bootstrap from examples:

```bash
cp .env.shared.example .env.shared
cp .env.shopping.example .env.shopping
```

## Run

From the **repository root**:

```bash
docker compose \
  -f infrastructure/docker/docker-compose.yml \
  --profile shared \
  --profile shopping \
  up --build
```

Profiles:

- `shared`: Mongo, Postgres/pgvector, Redis, Langfuse
- `shopping`: LiteLLM + API host with shopping plugin

## Services

| Service | Port | Role |
|---------|------|------|
| **api** | 8000 | FastAPI host (`llmops-api`): installs **llmops-core** + **shopping-assistant** + `apps/api` via `uv sync --all-packages` in the image |
| **mongo** | 27017 | Prompt store / operational data (host settings) |
| **postgres** | 5432 | `llmops` DB + `pgvector` extension; `langfuse` DB for Langfuse |
| **redis** | 6379 | Langfuse queue |
| **langfuse** | 3000 | Observability UI / API |
| **litellm** | 4000 | Model gateway (config: `litellm/config.yaml`) |

## Package install strategy (API image)

- **Build context:** monorepo root (see `Dockerfile.api` `COPY` paths).
- **Toolchain:** `uv sync --all-packages --no-dev` so workspace members resolve:
  - `packages/core` → `llmops-core`
  - `apps/api` → `llmops-api`
  - `packages/agents/shopping_assistant` → `shopping-assistant` (entry points registered for the host)
- **No** repo-root `data/` or shopping catalog paths are referenced; agent CLIs remain **package-local** (`shopping-assistant-catalog`, `shopping-assistant-seed-prompts`) inside the container’s installed package tree.

## Notes

- Langfuse and LiteLLM versions may need pinning if upstream images change; adjust `docker-compose.yml` as needed.
- For production, replace dev secrets and use managed databases / proper networking.
- If you only need infrastructure services, run `--profile shared` without `shopping`.
