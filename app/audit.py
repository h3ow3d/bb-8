from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _ensure_db(db_path: str) -> None:
    """Create the database directory and table if needed."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                token_fingerprint TEXT,
                cluster_context TEXT,
                resources_summary TEXT,
                checks_run TEXT,
                findings_count INTEGER DEFAULT 0,
                redaction_count INTEGER DEFAULT 0,
                ollama_model TEXT,
                status TEXT NOT NULL,
                error_summary TEXT,
                response_summary TEXT
            )
            """
        )
        conn.commit()


@contextmanager
def _get_conn(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    _ensure_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def write_audit(
    *,
    endpoint: str,
    token_fingerprint: str | None = None,
    cluster_context: str | None = None,
    resources_summary: str | None = None,
    checks_run: str | None = None,
    findings_count: int = 0,
    redaction_count: int = 0,
    ollama_model: str | None = None,
    status: str = "ok",
    error_summary: str | None = None,
    response_summary: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Write an audit record and return its ID."""
    if settings is None:
        settings = get_settings()
    record_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    try:
        with _get_conn(settings.audit_db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    id, timestamp, endpoint, token_fingerprint, cluster_context,
                    resources_summary, checks_run, findings_count, redaction_count,
                    ollama_model, status, error_summary, response_summary
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record_id,
                    ts,
                    endpoint,
                    token_fingerprint,
                    cluster_context,
                    resources_summary,
                    checks_run,
                    findings_count,
                    redaction_count,
                    ollama_model,
                    status,
                    error_summary,
                    response_summary,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.error("Failed to write audit record: %s", exc)
    return record_id


def get_recent_audit(limit: int = 20, settings: Settings | None = None) -> list[dict]:
    """Return the most recent audit records."""
    if settings is None:
        settings = get_settings()
    try:
        with _get_conn(settings.audit_db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("Failed to read audit records: %s", exc)
        return []
