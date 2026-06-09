# BB-8 Quick Start Guide

## Prerequisites

- Linux or macOS host with Docker Engine and Compose v2
- A kubeconfig with read access to your cluster
- (Optional) NVIDIA GPU + NVIDIA Container Toolkit for GPU-accelerated LLM inference

## Step 1: Get the files

Download the release bundle from GitHub Releases or clone the repository:

```bash
# From GitHub Releases:
tar xzf bb-8-mvp-v0.1.0.tar.gz
cd bb-8-mvp-v0.1.0

# Or from source:
git clone https://github.com/h3ow3d/bb-8.git
cd bb-8
```

## Step 2: Configure

```bash
cp deploy/compose/.env.example deploy/compose/.env
```

Edit `deploy/compose/.env`:

```bash
# Set a strong API token
SIDECAR_API_TOKEN=my-strong-random-token-here

# Path to your kubeconfig on the host
KUBECONFIG_PATH=/home/user/.kube/config

# Optional: specific Kubernetes context
K8S_CONTEXT=my-cluster-context

# Ollama model (must be pulled separately)
OLLAMA_MODEL=qwen2.5:7b-instruct
```

## Step 3: Pull the Ollama model

**This step requires internet access.** Run it before entering air-gapped mode.

```bash
scripts/pull-model.sh
```

The default model (`qwen2.5:7b-instruct`) is approximately 4-5 GB. On an RTX 3070 or similar 8GB VRAM GPU, it runs comfortably.

For CPU-only inference, the same model works but is slower (~30-60s per response).

## Step 4: Start BB-8

```bash
scripts/run.sh
```

Or manually:

```bash
docker compose -f deploy/compose/docker-compose.yml --env-file deploy/compose/.env up -d
```

## Step 5: Verify

```bash
# Health check (no auth)
curl http://localhost:8080/health

# Expected: {"status":"ok","version":"0.1.0","details":{}}
```

## Step 6: Run a cluster review

```bash
TOKEN="my-strong-random-token-here"

curl -s -X POST http://localhost:8080/v1/cluster/review \
  -H "Authorization: ******" \
  | python3 -m json.tool
```

The response includes:
- `summary` — high-level overview
- `priority_findings` — critical and high severity issues
- `health_findings` — health and operational issues
- `security_findings` — security and RBAC issues
- `recommended_next_checks` — suggested follow-up actions
- `llm_explanation` — local LLM narrative (empty if Ollama unavailable)
- `warnings` — non-fatal warnings (e.g., Ollama unavailable)
- `metadata` — cluster context, model, audit ID

## Step 7: Ask a question

```bash
curl -s -X POST http://localhost:8080/v1/ask \
  -H "Authorization: ******" \
  -H "Content-Type: application/json" \
  -d '{"question": "Which workloads are missing readiness probes?"}' \
  | python3 -m json.tool
```

## Step 8: View audit records

```bash
curl -s http://localhost:8080/v1/audit/recent \
  -H "Authorization: ******" \
  | python3 -m json.tool
```

## Troubleshooting

### "Kubernetes unavailable" error
- Verify `KUBECONFIG_PATH` in `.env` points to a valid kubeconfig file.
- Verify the context has read access to the cluster.

### "LLM explanation unavailable"
- Run `scripts/pull-model.sh` to download the model.
- Check `docker logs bb8-ollama` for errors.
- Without Ollama, deterministic findings are still returned.

### "Invalid bearer token" (401)
- Verify `SIDECAR_API_TOKEN` in `.env` matches the token in your request.

## Stopping

```bash
scripts/stop.sh
```

## Air-gapped use

Before disconnecting from the internet:

1. Pull the agent image: `docker pull ghcr.io/h3ow3d/bb-8-agent:v0.1.0`
2. Pull the Ollama model: `scripts/pull-model.sh`
3. Export images if needed for transfer to an offline host.

Once offline, BB-8 runs entirely from local Docker images and cached model weights.
