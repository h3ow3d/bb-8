# BB-8 MVP Scope

## In scope for MVP v0.1

### Deployment
- [x] Docker Compose deployment with `agent-api` and `ollama` services
- [x] Localhost-only API exposure (`127.0.0.1:8080`)
- [x] Named volumes for Ollama model data and audit data
- [x] Read-only kubeconfig mount
- [x] NVIDIA GPU support configuration (requires compatible host)

### Authentication & security
- [x] Bearer-token authentication for all `/v1/*` endpoints
- [x] Public `/health` endpoint
- [x] Token fingerprinting in audit logs (no full token stored)
- [x] HTTP 401 for missing or invalid tokens

### Kubernetes access
- [x] Read-only Kubernetes access via kubeconfig
- [x] Least-privilege RBAC manifest (`deploy/k8s/readonly-rbac.yaml`)
- [x] Collection of safe non-secret resources
- [x] Support for EKS, on-prem Kubernetes, k3s, and standard Kubernetes APIs
- [x] No Secrets access
- [x] No write, exec, attach, port-forward, proxy, impersonation, or escalate operations

### Evidence extraction
- [x] Health findings (pods, deployments, statefulsets, daemonsets, jobs, nodes, events)
- [x] Operational quality findings (missing resource requests/limits, missing probes, missing quotas)
- [x] Security posture findings (privileged containers, root containers, hostPath, hostNetwork, hostPID, hostIPC, LoadBalancer services, ingress exposure, missing network policies, broad RBAC)

### LLM integration
- [x] Local Ollama inference
- [x] Graceful fallback when Ollama is unavailable
- [x] Graceful fallback when model is not pulled
- [x] Redaction of sensitive data before sending to LLM
- [x] System prompt enforcing read-only reasoning assistant behaviour
- [x] Local knowledge directory for optional context injection

### API endpoints
- [x] `GET /health` — public health check
- [x] `POST /v1/cluster/review` — full cluster review
- [x] `POST /v1/ask` — free-form question to LLM
- [x] `GET /v1/audit/recent` — recent audit records

### Audit logging
- [x] SQLite audit log
- [x] Per-request records with token fingerprint, findings count, redaction count, model, status

### CI/CD
- [x] GitHub Actions PR checks (ruff, mypy, pytest, bandit, pip-audit, docker build, trivy)
- [x] GitHub Actions release workflow (GHCR publish, SBOM, release bundle)
- [x] Release bundle `bb-8-mvp-<version>.tar.gz` attached to GitHub Release

### Documentation
- [x] README.md with usage and architecture
- [x] QUICKSTART.md
- [x] SECURITY_MODEL.md
- [x] MODEL_STRATEGY.md
- [x] MVP_SCOPE.md

## Out of scope for MVP v0.1

- ❌ Web UI / frontend
- ❌ OIDC / multi-user authentication
- ❌ Multi-cluster support
- ❌ Vector database / semantic search in knowledge base
- ❌ Full vulnerability scanning (CVE databases)
- ❌ Full policy engine (OPA/Gatekeeper equivalent)
- ❌ Kubernetes Secrets inspection (by design)
- ❌ Pod log ingestion
- ❌ Automatic remediation of any kind
- ❌ Helm chart deployment
- ❌ In-cluster deployment (sidecar or operator)
- ❌ Fully offline bundle with embedded model weights
- ❌ Vendor-specific adapters (EKS-specific, GKE-specific, OpenShift-specific APIs)
- ❌ mTLS between containers
- ❌ High-availability or multi-replica deployment

## Roadmap ideas (future versions)

- Local vector database (ChromaDB or Qdrant) for semantic knowledge retrieval
- Namespace-scoped review mode
- Per-namespace health summaries
- Historical trend tracking in SQLite
- Export findings as JSON/CSV
- Integration with Prometheus metrics for context enrichment
- Fully offline Docker-in-Docker bundle mode
