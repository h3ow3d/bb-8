"""Tests for bearer-token authentication."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import _token_fingerprint
from app.config import Settings, get_settings
from app.main import app

_TEST_TOKEN = "test-api-token-abc123"
_BEARER_HEADER = "Bearer " + _TEST_TOKEN
_WRONG_HEADER = "******"


def _make_settings(**kwargs):
    defaults = {
        "sidecar_api_token": _TEST_TOKEN,
        "kubeconfig": "/nonexistent/kubeconfig",
        "audit_db_path": "/tmp/test-auth-audit.db",
    }
    defaults.update(kwargs)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


class TestTokenFingerprint:
    def test_fingerprint_is_12_chars(self):
        fp = _token_fingerprint("my-secret-token")
        assert len(fp) == 12

    def test_same_token_same_fingerprint(self):
        assert _token_fingerprint("abc") == _token_fingerprint("abc")

    def test_different_tokens_different_fingerprints(self):
        assert _token_fingerprint("token-a") != _token_fingerprint("token-b")

    def test_fingerprint_does_not_contain_full_token(self):
        token = "super-secret-value-here"
        fp = _token_fingerprint(token)
        assert token not in fp


class TestAuthMiddleware:
    def test_health_requires_no_auth(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_missing_token_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/v1/audit/recent")
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self):
        app.dependency_overrides[get_settings] = lambda: _make_settings(
            sidecar_api_token="correct-token"
        )
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/v1/audit/recent",
            headers={"Authorization": _WRONG_HEADER},
        )
        assert resp.status_code == 401

    def test_correct_token_allows_access(self):
        app.dependency_overrides[get_settings] = lambda: _make_settings()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/v1/audit/recent",
            headers={"Authorization": _BEARER_HEADER},
        )
        assert resp.status_code == 200

    def test_non_bearer_scheme_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/v1/audit/recent",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401

    def test_empty_bearer_returns_401(self):
        app.dependency_overrides[get_settings] = lambda: _make_settings()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/v1/audit/recent",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401
