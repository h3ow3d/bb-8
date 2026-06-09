"""Tests for audit logging."""
from __future__ import annotations

import os

import pytest

from app.audit import get_recent_audit, write_audit
from app.config import Settings


@pytest.fixture
def audit_settings(tmp_path):
    db_path = str(tmp_path / "test.db")
    return Settings(
        sidecar_api_token="test-token",
        audit_db_path=db_path,
    )


class TestWriteAudit:
    def test_write_returns_string_id(self, audit_settings):
        audit_id = write_audit(
            endpoint="/health",
            settings=audit_settings,
        )
        assert isinstance(audit_id, str)
        assert len(audit_id) > 0

    def test_write_creates_db(self, audit_settings):
        write_audit(endpoint="/v1/cluster/review", settings=audit_settings)
        assert os.path.exists(audit_settings.audit_db_path)

    def test_write_with_all_fields(self, audit_settings):
        audit_id = write_audit(
            endpoint="/v1/cluster/review",
            token_fingerprint="abc123",
            cluster_context="my-cluster",
            resources_summary="nodes=3 pods=10",
            checks_run="health,security",
            findings_count=5,
            redaction_count=2,
            ollama_model="qwen2.5:7b-instruct",
            status="ok",
            response_summary="5 findings",
            settings=audit_settings,
        )
        assert audit_id

    def test_multiple_writes(self, audit_settings):
        ids = []
        for i in range(5):
            audit_id = write_audit(
                endpoint=f"/endpoint/{i}",
                settings=audit_settings,
            )
            ids.append(audit_id)
        assert len(set(ids)) == 5  # all unique


class TestGetRecentAudit:
    def test_empty_db_returns_empty_list(self, audit_settings):
        records = get_recent_audit(settings=audit_settings)
        assert records == []

    def test_returns_records_after_write(self, audit_settings):
        write_audit(
            endpoint="/v1/ask",
            token_fingerprint="fp123",
            status="ok",
            settings=audit_settings,
        )
        records = get_recent_audit(settings=audit_settings)
        assert len(records) == 1
        assert records[0]["endpoint"] == "/v1/ask"

    def test_returns_most_recent_first(self, audit_settings):
        for ep in ["/a", "/b", "/c"]:
            write_audit(endpoint=ep, settings=audit_settings)
        records = get_recent_audit(limit=3, settings=audit_settings)
        assert len(records) == 3
        # Most recent should be first
        assert records[0]["endpoint"] == "/c"

    def test_limit_respected(self, audit_settings):
        for i in range(10):
            write_audit(endpoint=f"/ep/{i}", settings=audit_settings)
        records = get_recent_audit(limit=3, settings=audit_settings)
        assert len(records) == 3

    def test_token_fingerprint_stored_not_full_token(self, audit_settings):
        write_audit(
            endpoint="/v1/cluster/review",
            token_fingerprint="fp_abc123",
            settings=audit_settings,
        )
        records = get_recent_audit(settings=audit_settings)
        assert records[0]["token_fingerprint"] == "fp_abc123"
