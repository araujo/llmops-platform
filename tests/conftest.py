"""Shared fixtures for LLMOps platform tests."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_plugin_discovery_skip() -> Generator[None, None, None]:
    """Ensure plugin discovery runs unless a test overrides this."""
    os.environ.pop("LLMOPS_SKIP_PLUGIN_DISCOVERY", None)
    yield
    os.environ.pop("LLMOPS_SKIP_PLUGIN_DISCOVERY", None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Full ASGI app with lifespan (Mongo optional; shopping plugin discovered)."""
    from llmops_api.main import app

    with TestClient(app) as test_client:
        yield test_client
