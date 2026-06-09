from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["info", "low", "medium", "high", "critical"]
Category = Literal["health", "operational", "security", "rbac", "networking"]


@dataclass
class Finding:
    id: str
    title: str
    severity: Severity
    category: Category
    resource_ref: str = ""
    namespace: str = ""
    evidence: str = ""
    recommendation: str = ""


def make_finding(
    *,
    id: str,
    title: str,
    severity: Severity,
    category: Category,
    resource_ref: str = "",
    namespace: str = "",
    evidence: str = "",
    recommendation: str = "",
) -> Finding:
    return Finding(
        id=id,
        title=title,
        severity=severity,
        category=category,
        resource_ref=resource_ref,
        namespace=namespace,
        evidence=evidence,
        recommendation=recommendation,
    )


SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))
