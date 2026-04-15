"""Thin FastAPI host: operational routes + plugin routers loaded via ``llmops-core``."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as pkg_version

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

from llmops_api.lifecycle import lifespan


def _api_version() -> str:
    try:
        return pkg_version("llmops-api")
    except PackageNotFoundError:
        return "0.0.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="LLMOps API",
        version=_api_version(),
        lifespan=lifespan,
    )

    @app.get("/")
    async def root(request: Request) -> dict[str, str]:
        settings = request.app.state.settings
        return {
            "service": settings.service_name,
            "version": _api_version(),
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> Response:
        data = generate_latest(REGISTRY)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("llmops_api.main:app", host="0.0.0.0", port=8000)
