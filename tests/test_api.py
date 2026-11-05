from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from emporio.api import create_app
from emporio.config import Settings
from emporio.service import AgentUnavailable, ChatService


@pytest.fixture
def service(tmp_path):
    return ChatService(
        Settings(provider="demo", state_dir=tmp_path, data_dir=Path("data"), _env_file=None)
    )


@pytest.fixture
def client(service):
    with TestClient(create_app(service=service)) as client:
        yield client


def session(client):
    response = client.post("/api/sessions")
    assert response.status_code == 201
    data = response.json()
    return data["session_id"], {"Authorization": f"Bearer {data['token']}"}


def test_public_health_catalog_and_document(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["provider"] == "demo"
    assert health.json()["counts"]["products"] > 0
    products = client.get("/api/products", params={"max_price_brl": 1000}).json()["products"]
    assert products
    assert all(p["available"] and p["sale_price_cents"] <= 100000 for p in products)
    pdf = client.get("/api/policies/document")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_sessions_are_protected_and_cannot_be_enumerated(client):
    first, headers = session(client)
    second, other = session(client)
    assert first != second
    for suffix, method, body in [
        ("", "get", None),
        ("", "delete", None),
        ("/messages", "post", {"message": "Oi"}),
        ("/order-access", "post", {"order_id": 1, "email": "a@b.com"}),
    ]:
        path = f"/api/sessions/{first}{suffix}"
        kwargs = {"json": body} if body is not None else {}
        assert client.request(method, path, **kwargs).status_code == 401
        assert client.request(method, path, headers=other, **kwargs).status_code == 404
    assert client.get(f"/api/sessions/{first}", headers=headers).json() == {
        "session_id": first,
        "messages": [],
        "verified_orders": [],
    }


def test_chat_history_and_delete(client):
    sid, headers = session(client)
    response = client.post(
        f"/api/sessions/{sid}/messages",
        headers=headers,
        json={"message": "  Qual o horário de funcionamento?  "},
    )
    assert response.status_code == 200
    assert response.json()["message"]
    assert response.json()["sources"]
    history = client.get(f"/api/sessions/{sid}", headers=headers).json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["content"] == "Qual o horário de funcionamento?"
    assert response.json()["latency_ms"] >= 0
    assert history[1].get("latency_ms") == response.json()["latency_ms"]
    assert client.get(f"/api/sessions/{sid}/history", headers=headers).json() == history
    assert client.delete(f"/api/sessions/{sid}", headers=headers).status_code == 204
    assert client.get(f"/api/sessions/{sid}", headers=headers).status_code == 404


@pytest.mark.parametrize("message", ["", "  \n ", "x" * 4001])
def test_invalid_message_rejected(client, message):
    sid, headers = session(client)
    assert (
        client.post(
            f"/api/sessions/{sid}/messages", headers=headers, json={"message": message}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"order_id": 0, "email": "a@b.com"},
        {"order_id": 1, "email": "inválido"},
        {"order_id": 1, "email": "a" * 255 + "@b.com"},
    ],
)
def test_invalid_verification_rejected(client, payload):
    sid, headers = session(client)
    assert (
        client.post(f"/api/sessions/{sid}/order-access", headers=headers, json=payload).status_code
        == 422
    )


def test_failed_verification_has_generic_error_and_rate_limit(client):
    sid, headers = session(client)
    path = f"/api/sessions/{sid}/order-access"
    for _ in range(5):
        response = client.post(
            path, headers=headers, json={"order_id": 99999999, "email": "nobody@example.com"}
        )
        assert response.status_code == 403
        assert "nobody" not in response.text
    limited = client.post(
        path, headers=headers, json={"order_id": 99999999, "email": "nobody@example.com"}
    )
    assert limited.status_code == 429


def test_order_grants_stay_in_the_verified_session(client):
    sid, headers = session(client)
    second, other = session(client)
    result = client.post(
        f"/api/sessions/{sid}/order-access",
        headers=headers,
        json={"order_id": 1, "email": "pedro.oliveira@jmail.com"},
    )
    assert result.status_code == 200
    assert result.json() == {"verified": True, "order_id": 1}
    assert client.get(f"/api/sessions/{sid}", headers=headers).json()["verified_orders"] == [1]
    assert client.get(f"/api/sessions/{second}", headers=other).json()["verified_orders"] == []


def test_second_turn_in_a_busy_session_returns_conflict(client, service):
    sid, headers = session(client)
    with service.sessions.turn(sid):
        response = client.post(
            f"/api/sessions/{sid}/messages", headers=headers, json={"message": "Olá"}
        )
    assert response.status_code == 409


def test_provider_errors_do_not_expose_details(client, service, monkeypatch):
    def fail(*args):
        raise AgentUnavailable("SECRET API KEY TRACEBACK")

    monkeypatch.setattr(service, "chat", fail)
    sid, headers = session(client)
    response = client.post(
        f"/api/sessions/{sid}/messages", headers=headers, json={"message": "Olá"}
    )
    assert response.status_code == 503
    assert "SECRET" not in response.text


def test_unexpected_errors_are_sanitized_and_keep_security_headers(client, service, monkeypatch):
    def fail(*args):
        raise RuntimeError("SECRET traceback")

    monkeypatch.setattr(service, "chat", fail)
    sid, headers = session(client)
    response = client.post(
        f"/api/sessions/{sid}/messages", headers=headers, json={"message": "Olá"}
    )
    assert response.status_code == 500
    assert "SECRET" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_security_headers_static_and_query_validation(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Mel" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200
    for params in [{"limit": 0}, {"limit": 31}, {"max_price_brl": -1}]:
        assert client.get("/api/products", params=params).status_code == 422
    assert "access-control-allow-origin" not in client.get("/api/health").headers


def test_factory_defers_initialization_until_startup(tmp_path):
    state = tmp_path / "untouched"
    app = create_app(
        Settings(provider="demo", state_dir=state, data_dir=Path("data"), _env_file=None)
    )
    assert not state.exists()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
    assert state.exists()
