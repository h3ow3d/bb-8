from __future__ import annotations

from app.rules.findings import Finding

_SYSTEM_PROMPT = """You are BB-8, a Kubernetes, cloud-native, and Kubernetes security assistant.

Your role:
- Reason only from the evidence and local knowledge provided to you.
- Do not claim you directly inspected the cluster or have access to it.
- Do not ask for secrets, credentials, or any sensitive data.
- Do not suggest automated write or remediation commands.
- If a user asks you to read Secrets, exec into pods, delete resources, patch resources,
  port-forward, or dump environment variables, refuse safely and explain the boundary.
- Clearly separate: facts from the evidence, likely causes, risks, and recommended next checks.
- Cite specific resource references from the evidence (e.g., Pod/my-app, Deployment/backend).
- Say clearly when evidence is insufficient to make a confident assessment.
- Keep your response focused, structured, and actionable.
"""


def build_review_messages(
    context: str,
    findings: list[Finding],
    knowledge_snippets: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build the chat messages for a cluster review."""
    evidence_parts = [f"Cluster context: {context}"]

    if findings:
        evidence_parts.append(f"\nFindings ({len(findings)} total):")
        for f in findings[:50]:  # Cap at 50 findings to avoid context overflow
            evidence_parts.append(
                f"  [{f.severity.upper()}][{f.category}] {f.title}\n"
                f"    resource: {f.resource_ref} namespace: {f.namespace}\n"
                f"    evidence: {f.evidence}\n"
                f"    recommendation: {f.recommendation}"
            )
    else:
        evidence_parts.append("\nNo issues found in automated checks.")

    if knowledge_snippets:
        evidence_parts.append("\n--- Local Knowledge ---")
        for doc in knowledge_snippets:
            evidence_parts.append(f"\n# {doc.get('filename', '')}\n{doc.get('content', '')}")

    user_content = "\n".join(evidence_parts)
    user_content += (
        "\n\nBased on the above evidence, provide a structured cluster health and security review. "
        "Include: summary, priority findings, health analysis, security posture, and recommended next checks."
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_ask_messages(
    question: str,
    context: str,
    knowledge_snippets: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build the chat messages for a free-form question."""
    parts = [f"Question: {question}"]
    if context:
        parts.append(f"\nContext provided by user:\n{context}")
    if knowledge_snippets:
        parts.append("\n--- Local Knowledge ---")
        for doc in knowledge_snippets:
            parts.append(f"\n# {doc.get('filename', '')}\n{doc.get('content', '')}")

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]
