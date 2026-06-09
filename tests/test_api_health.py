"""Tests for /health endpoint and FastAPI app setup."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_returns_ok_status():
    client = TestClient(app)
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"


def test_health_returns_version():
    client = TestClient(app)
    resp = client.get("/health")
    data = resp.json()
    assert "version" in data


def test_health_no_auth_required():
    client = TestClient(app)
    # No Authorization header - should still succeed
    resp = client.get("/health")
    assert resp.status_code == 200


def test_docs_available():
    client = TestClient(app)
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_audit_recent_requires_auth():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/v1/audit/recent")
    assert resp.status_code == 401


def test_cluster_review_requires_auth():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/v1/cluster/review")
    assert resp.status_code == 401


def test_ask_requires_auth():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/v1/ask", json={"question": "hello"})
    assert resp.status_code == 401
