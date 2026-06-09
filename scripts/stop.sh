#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/compose/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/deploy/compose/.env"

echo "🛑 Stopping BB-8 Kubernetes Sidekick..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
echo "✅ BB-8 stopped."
