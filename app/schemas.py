from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "low", "medium", "high", "critical"]
Category = Literal["health", "operational", "security", "rbac", "networking"]


class Finding(BaseModel):
    id: str
    title: str
    severity: Severity
    category: Category
    resource_ref: str = ""
    namespace: str = ""
    evidence: str = ""
    recommendation: str = ""


class ClusterReviewMetadata(BaseModel):
    cluster_context: str = ""
    model: str = ""
    redaction_count: int = 0
    audit_id: str = ""


class ClusterReviewResponse(BaseModel):
    summary: str = ""
    priority_findings: list[Finding] = Field(default_factory=list)
    health_findings: list[Finding] = Field(default_factory=list)
    security_findings: list[Finding] = Field(default_factory=list)
    recommended_next_checks: list[str] = Field(default_factory=list)
    llm_explanation: str = ""
    warnings: list[str] = Field(default_factory=list)
    metadata: ClusterReviewMetadata = Field(default_factory=ClusterReviewMetadata)


class AskRequest(BaseModel):
    question: str
    context: str = ""


class AskResponse(BaseModel):
    answer: str
    model: str = ""
    audit_id: str = ""
    warnings: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    id: str
    timestamp: str
    endpoint: str
    token_fingerprint: str | None = None
    cluster_context: str | None = None
    resources_summary: str | None = None
    checks_run: str | None = None
    findings_count: int = 0
    redaction_count: int = 0
    ollama_model: str | None = None
    status: str = "ok"
    error_summary: str | None = None
    response_summary: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    details: dict[str, Any] = Field(default_factory=dict)
