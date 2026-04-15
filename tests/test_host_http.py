"""FastAPI host HTTP surface and shopping agent routes (deterministic catalog)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_host_startup_and_operational_endpoints(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "llmops-api"
    assert "version" in body

    h = client.get("/health")
    assert h.status_code == 200
    assert h.json() == {"status": "ok"}

    m = client.get("/metrics")
    assert m.status_code == 200
    assert "text/plain" in m.headers.get("content-type", "")
    assert b"python_gc_objects_collected_total" in m.content or b"# HELP" in m.content


def test_openapi_includes_shopping_routes_under_v1_agents(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/v1/agents/shopping_assistant/info" in paths
    assert "/v1/agents/shopping_assistant/chat/shopping" in paths
    assert "get" in paths["/v1/agents/shopping_assistant/info"]
    assert "post" in paths["/v1/agents/shopping_assistant/chat/shopping"]


def test_get_shopping_info(client: TestClient) -> None:
    r = client.get("/v1/agents/shopping_assistant/info")
    assert r.status_code == 200
    data = r.json()
    assert data["agent_id"] == "shopping_assistant"
    assert data["package_version"]


def test_post_shopping_chat_deterministic_baseline(client: TestClient) -> None:
    """Structured response from catalog search / filter / rank."""
    r = client.post(
        "/v1/agents/shopping_assistant/chat/shopping",
        json={"message": "Wireless headphones under $400"},
    )
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {
        "reply",
        "mode",
        "preferences",
        "search_plan",
        "products",
    }
    assert data["mode"] == "deterministic"
    assert data["products"]
    assert data["preferences"] is not None
    assert data["search_plan"] is not None
    assert "headphones" in data["reply"].lower() or any(
        "headphone" in (p.get("name") or "").lower() for p in data["products"]
    )


def test_integration_full_request_flow(client: TestClient) -> None:
    """Integration-style: single client session exercises host + mounted plugin."""
    assert client.get("/health").json()["status"] == "ok"
    info = client.get("/v1/agents/shopping_assistant/info").json()
    assert info["agent_id"] == "shopping_assistant"
    chat = client.post(
        "/v1/agents/shopping_assistant/chat/shopping",
        json={"message": "Show me a cheap kitchen blender"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["mode"] == "deterministic"
    assert body["products"]
