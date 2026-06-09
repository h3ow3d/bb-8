# BB-8 Security Model

## Overview

BB-8 is designed for security-conscious environments. This document describes the security boundaries, constraints, and known limitations.

## VM boundary

BB-8 runs on a VM (or host machine) under your control. It does not phone home, it does not call external APIs, and it does not require internet access at runtime. All processing is local.

## Agent vs LLM separation

The `agent-api` container and the `ollama` container are separated:

| Concern | agent-api | ollama |
|---------|-----------|--------|
| Kubeconfig | ✅ Mounted read-only | ❌ Not mounted |
| Kubernetes API access | ✅ Via kubeconfig | ❌ None |
| Internet access | ❌ Not required at runtime | ❌ Not required at runtime |
| LLM inference | ❌ Delegated to Ollama | ✅ Yes |

The `ollama` container only receives curated, redacted evidence from `agent-api`. It cannot access the cluster directly.

## Kubeconfig

- Mounted read-only into `agent-api` only.
- `ollama` has no access to kubeconfig.
- The agent uses the Kubernetes Python client with the configured context.
- No Kubernetes credentials are embedded in the image.

## What BB-8 reads

BB-8 collects read-only metadata using `get`, `list`, and `watch` verbs only:

- Namespaces, nodes, pods, services, endpoints, events
- Deployments, ReplicaSets, DaemonSets, StatefulSets
- Jobs, CronJobs
- Ingresses, NetworkPolicies
- ServiceAccounts, Roles, RoleBindings, ClusterRoles, ClusterRoleBindings
- ResourceQuotas, LimitRanges, PodDisruptionBudgets

## What BB-8 does NOT read

- ❌ Kubernetes Secrets (excluded by design and by RBAC)
- ❌ Raw pod logs
- ❌ Pod exec output
- ❌ Container environment variable values
- ❌ PersistentVolume contents
- ❌ Config file contents from containers

## No write operations

BB-8 never calls:

- `create`, `update`, `patch`, `delete` verbs
- `pods/exec`, `pods/attach`, `pods/portforward`
- `services/proxy`, `nodes/proxy`
- `serviceaccounts/token`
- Impersonation, bind, or escalate
- Token reviews or subject access reviews

## Redaction before LLM

Before any data is sent to the local Ollama model, BB-8 applies redaction:

- Token-like strings are replaced with `[REDACTED]`
- Password-like values are replaced with `[REDACTED]`
- Connection strings are replaced with `[REDACTED]`
- Private key material is replaced with `[REDACTED]`
- Base64-encoded blobs that look like secrets are replaced with `[REDACTED]`
- Dictionary keys matching sensitive patterns are redacted

Kubernetes-sourced text is treated as untrusted input. It cannot override system instructions.

The number of redactions is counted and included in audit metadata.

## Local-only inference

The Ollama model runs locally. No data is sent to OpenAI, Anthropic, Google, or any other external service.

## Authentication

- All `/v1/*` endpoints require a bearer token.
- The token is configured via `SIDECAR_API_TOKEN` environment variable.
- The full token value is never logged.
- Audit logs store only a short SHA-256 fingerprint of the token.
- The API is exposed on `127.0.0.1:8080` by default (localhost only).

## Audit logging

Every authenticated request is logged to a local SQLite database at `AUDIT_DB_PATH`. Logs include:

- Timestamp and request ID
- Endpoint called
- Token fingerprint (not the full token)
- Cluster context
- Summary of resources queried
- Number and type of checks run
- Number of findings
- Redaction count
- Ollama model name
- Status (ok, error, refused, etc.)
- Short response summary

Raw Kubernetes snapshots are NOT stored by default.

## Network isolation

The Docker Compose stack uses a private bridge network `bb8-net`. Only `agent-api` is exposed on the host (port 8080, localhost only).

## Known limitations

- The token is a single shared secret. For multi-user environments, consider additional access controls at the network or reverse-proxy layer.
- The MVP does not support mTLS between containers.
- The MVP does not support OIDC.
- The redaction heuristics are best-effort, not a guaranteed DLP solution.
- The RBAC manifest requires cluster-level read permissions. In very restricted environments, a namespace-scoped Role may be more appropriate for some resources.
- Container image vulnerability scanning is not performed at runtime.
