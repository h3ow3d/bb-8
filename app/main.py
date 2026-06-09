from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from app.audit import get_recent_audit, write_audit
from app.auth import verify_token
from app.config import Settings, get_settings
from app.k8s.client import get_current_context, load_kube_client
from app.k8s.collectors import collect_snapshot
from app.knowledge.local_docs import load_docs, retrieve_relevant
from app.llm.ollama_client import OllamaError, OllamaModelMissingError, OllamaUnavailableError, chat
from app.llm.prompts import build_ask_messages, build_review_messages
from app.redaction.redactor import redact_text
from app.rules.findings import Finding, sort_findings
from app.rules.health import run_all_health_checks
from app.rules.security import run_all_security_checks
from app.schemas import (
    AskRequest,
    AskResponse,
    AuditRecord,
    ClusterReviewMetadata,
    ClusterReviewResponse,
    HealthResponse,
)
from app.schemas import Finding as SchemaFinding

logger = logging.getLogger(__name__)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    _setup_logging(settings.log_level)
    logger.info("BB-8 Kubernetes Sidekick starting up")
    yield
    logger.info("BB-8 Kubernetes Sidekick shutting down")


app = FastAPI(
    title="BB-8 Kubernetes Sidekick",
    version="0.1.0",
    description="Air-gapped Kubernetes sidekick with local LLM reasoning",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)


def _finding_to_schema(f: Finding) -> SchemaFinding:
    return SchemaFinding(
        id=f.id,
        title=f.title,
        severity=f.severity,
        category=f.category,
        resource_ref=f.resource_ref,
        namespace=f.namespace,
        evidence=f.evidence,
        recommendation=f.recommendation,
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Health check endpoint. No authentication required."""
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/v1/cluster/review", response_model=ClusterReviewResponse, tags=["cluster"])
async def cluster_review(
    token_fp: Annotated[str, Depends(verify_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClusterReviewResponse:
    """Collect cluster state, run checks, and get LLM analysis."""
    all_findings: list[Finding] = []
    redaction_count = 0
    context_name = ""
    response_summary = ""
    warnings: list[str] = []

    try:
        # Load k8s client
        try:
            api_client = load_kube_client(
                settings.kubeconfig,
                context=settings.k8s_context or None,
            )
            context_name = get_current_context(
                settings.kubeconfig,
                context=settings.k8s_context or None,
            )
        except Exception as exc:
            logger.error("Failed to connect to Kubernetes: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Kubernetes unavailable: {exc}",
            ) from exc

        # Collect snapshot
        try:
            snapshot = collect_snapshot(api_client)
            snapshot.context = context_name
        except Exception as exc:
            logger.error("Failed to collect cluster snapshot: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to collect cluster state: {exc}",
            ) from exc

        # Run checks
        health_findings = run_all_health_checks(snapshot)
        security_findings = run_all_security_checks(snapshot)
        all_findings = sort_findings(health_findings + security_findings)

        # Load knowledge
        docs = load_docs(settings.knowledge_dir)
        query = " ".join(f.title for f in all_findings[:10])
        relevant_docs = retrieve_relevant(docs, query)

        # Redact findings evidence before sending to LLM
        redacted_findings: list[Finding] = []
        for f in all_findings:
            ev, rc = redact_text(f.evidence)
            redaction_count += rc
            redacted_findings.append(
                Finding(
                    id=f.id,
                    title=f.title,
                    severity=f.severity,
                    category=f.category,
                    resource_ref=f.resource_ref,
                    namespace=f.namespace,
                    evidence=ev,
                    recommendation=f.recommendation,
                )
            )

        # Build LLM prompt
        messages = build_review_messages(context_name, redacted_findings, relevant_docs)

        # Query LLM — never fail the whole request on Ollama errors
        llm_explanation = ""
        try:
            llm_explanation = chat(
                settings.ollama_base_url,
                settings.ollama_model,
                messages,
            )
        except OllamaModelMissingError:
            warn_msg = (
                f"Local LLM explanation unavailable: model '{settings.ollama_model}' not found. "
                "Run scripts/pull-model.sh to download it."
            )
            logger.warning(warn_msg)
            warnings.append(warn_msg)
        except OllamaUnavailableError:
            warn_msg = (
                f"Local LLM explanation unavailable: could not reach Ollama at "
                f"{settings.ollama_base_url}. Ensure the ollama service is running."
            )
            logger.warning(warn_msg)
            warnings.append(warn_msg)
        except OllamaError as exc:
            warn_msg = f"Local LLM explanation unavailable: {exc}"
            logger.warning(warn_msg)
            warnings.append(warn_msg)

        # Categorize findings
        prio = [f for f in all_findings if f.severity in ("critical", "high")][:10]
        h_findings = [f for f in all_findings if f.category in ("health", "operational")]
        s_findings = [f for f in all_findings if f.category in ("security", "rbac", "networking")]

        response_summary = f"{len(all_findings)} findings, {len(prio)} priority"

        audit_id = write_audit(
            endpoint="/v1/cluster/review",
            token_fingerprint=token_fp,
            cluster_context=context_name,
            resources_summary=(
                f"nodes={len(snapshot.nodes)} pods={len(snapshot.pods)} "
                f"namespaces={len(snapshot.namespaces)}"
            ),
            checks_run="health,security",
            findings_count=len(all_findings),
            redaction_count=redaction_count,
            ollama_model=settings.ollama_model,
            status="ok",
            response_summary=response_summary,
            settings=settings,
        )

        return ClusterReviewResponse(
            summary=f"Cluster review complete. {len(all_findings)} findings identified.",
            priority_findings=[_finding_to_schema(f) for f in prio],
            health_findings=[_finding_to_schema(f) for f in h_findings],
            security_findings=[_finding_to_schema(f) for f in s_findings],
            recommended_next_checks=[
                "Review pod logs for crashlooping containers",
                "Check node resource utilization",
                "Review RBAC bindings for least privilege",
                "Ensure NetworkPolicies are in place",
            ],
            llm_explanation=llm_explanation,
            warnings=warnings,
            metadata=ClusterReviewMetadata(
                cluster_context=context_name,
                model=settings.ollama_model,
                redaction_count=redaction_count,
                audit_id=audit_id,
            ),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in cluster review: %s", exc)
        write_audit(
            endpoint="/v1/cluster/review",
            token_fingerprint=token_fp,
            status="error",
            error_summary=str(exc),
            settings=settings,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@app.post("/v1/ask", response_model=AskResponse, tags=["llm"])
async def ask(
    request: AskRequest,
    token_fp: Annotated[str, Depends(verify_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AskResponse:
    """Ask the local LLM a Kubernetes-related question."""
    # Safety check for dangerous operations
    _REFUSED_PATTERNS = [
        ("secret", "Reading Kubernetes Secrets is outside BB-8's access boundary."),
        ("exec", "Pod exec is not supported. BB-8 has read-only access."),
        ("delete", "BB-8 does not perform write/delete operations."),
        ("patch", "BB-8 does not perform write/patch operations."),
        ("port-forward", "Port-forwarding is not supported by BB-8."),
        ("environment variable", "BB-8 does not dump container environment variables."),
    ]
    question_lower = request.question.lower()
    for pattern, refusal in _REFUSED_PATTERNS:
        if pattern in question_lower and any(
            kw in question_lower for kw in ["show", "get", "list", "dump", "read", "exec", "delete", "patch"]
        ):
            audit_id = write_audit(
                endpoint="/v1/ask",
                token_fingerprint=token_fp,
                status="refused",
                response_summary=refusal,
                settings=settings,
            )
            return AskResponse(
                answer=refusal + " BB-8 supports read-only cluster metadata only.",
                model="",
                audit_id=audit_id,
                warnings=["Request refused: operation outside allowed boundary."],
            )

    # Redact context before sending to LLM
    redacted_ctx, redaction_count = redact_text(request.context)
    redacted_q, rq_count = redact_text(request.question)
    redaction_count += rq_count

    docs = load_docs(settings.knowledge_dir)
    relevant_docs = retrieve_relevant(docs, request.question)
    messages = build_ask_messages(redacted_q, redacted_ctx, relevant_docs)

    answer = ""
    warnings: list[str] = []

    try:
        answer = chat(
            settings.ollama_base_url,
            settings.ollama_model,
            messages,
        )
    except OllamaModelMissingError as exc:
        warn_msg = (
            f"Local LLM unavailable: model '{settings.ollama_model}' not found. "
            "Run scripts/pull-model.sh to download it."
        )
        answer = warn_msg
        warnings.append(warn_msg)
        audit_status = "llm_model_missing"
        error_summary = str(exc)
    except OllamaUnavailableError as exc:
        warn_msg = (
            f"Local LLM unavailable: could not reach Ollama at {settings.ollama_base_url}."
        )
        answer = warn_msg
        warnings.append(warn_msg)
        audit_status = "llm_unavailable"
        error_summary = str(exc)
    except OllamaError as exc:
        warn_msg = f"Local LLM error: {exc}"
        answer = warn_msg
        warnings.append(warn_msg)
        audit_status = "llm_error"
        error_summary = str(exc)

    audit_id = write_audit(
        endpoint="/v1/ask",
        token_fingerprint=token_fp,
        redaction_count=redaction_count,
        ollama_model=settings.ollama_model,
        status=audit_status,
        error_summary=error_summary,
        response_summary=answer[:200] if answer else None,
        settings=settings,
    )

    return AskResponse(
        answer=answer,
        model=settings.ollama_model,
        audit_id=audit_id,
        warnings=warnings,
    )


@app.get("/v1/audit/recent", response_model=list[AuditRecord], tags=["audit"])
async def audit_recent(
    token_fp: Annotated[str, Depends(verify_token)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AuditRecord]:
    """Return recent audit records."""
    records = get_recent_audit(limit=20, settings=settings)
    return [AuditRecord(**r) for r in records]
