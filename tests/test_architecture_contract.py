"""Architecture invariants: no legacy generic routes; host and core stay agent-agnostic."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TOP_LEVEL_PATHS = frozenset({"/chat", "/rag", "/documents", "/prompts"})


def test_openapi_paths_exclude_generic_platform_surfaces(client: TestClient) -> None:
    """No repo-wide /chat, /rag, /documents, or /prompts (agent-specific paths are OK)."""
    openapi = client.get("/openapi.json").json()
    paths = set(openapi["paths"])
    assert FORBIDDEN_TOP_LEVEL_PATHS.isdisjoint(paths)


def test_host_llmops_api_has_no_shopping_assistant_imports() -> None:
    """``apps/api`` must not import agent packages by name."""
    host_dir = REPO_ROOT / "apps" / "api" / "llmops_api"
    assert host_dir.is_dir()
    for path in sorted(host_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "shopping_assistant" not in text, (
            f"Host must remain agent-agnostic: found 'shopping_assistant' in {path}"
        )


def test_core_llmops_core_has_no_shopping_domain_references() -> None:
    """``llmops-core`` Python sources must not reference the shopping agent."""
    core_dir = REPO_ROOT / "packages" / "core" / "llmops_core"
    assert core_dir.is_dir()
    for path in sorted(core_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "shopping_assistant" not in text, (
            f"Core must stay agent-agnostic: found 'shopping_assistant' in {path}"
        )
        assert "packages/agents/shopping" not in text
