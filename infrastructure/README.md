# Infrastructure

Docker-based local stack for the LLMOps monorepo lives under **`docker/`**:

- `docker/docker-compose.yml` — MongoDB, PostgreSQL (pgvector), Redis, Langfuse, LiteLLM, API host
- `docker/Dockerfile.api` — builds the FastAPI host with `uv` workspace install (core + API + shopping agent)

See [docker/README.md](docker/README.md) for commands and service summary.
