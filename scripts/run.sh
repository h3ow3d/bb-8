#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/deploy/compose/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/deploy/compose/.env"
ENV_EXAMPLE="${REPO_ROOT}/deploy/compose/.env.example"

echo "🤖 BB-8 Kubernetes Sidekick"
echo "============================="

# Check Docker
if ! command -v docker &>/dev/null; then
    echo "❌ Docker is not installed or not in PATH."
    echo "   Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "❌ Docker daemon is not running."
    echo "   Start Docker and try again."
    exit 1
fi

# Check .env
if [ ! -f "${ENV_FILE}" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    echo "   Edit ${ENV_FILE} and set SIDECAR_API_TOKEN before running."
    echo "   Then run this script again."
    exit 1
fi

# Check that the token has been changed from the default
if grep -q "SIDECAR_API_TOKEN=change-me" "${ENV_FILE}"; then
    echo "⚠️  WARNING: SIDECAR_API_TOKEN is still set to 'change-me'."
    echo "   Set a strong token in ${ENV_FILE} before exposing the API."
fi

echo "▶  Starting BB-8 stack..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d

echo ""
echo "✅ BB-8 is running!"
echo ""
echo "   Health check:   curl http://localhost:8080/health"
echo ""
echo "   To call protected endpoints, get your token from ${ENV_FILE} and run:"
echo "     TOKEN=\$(grep SIDECAR_API_TOKEN ${ENV_FILE} | cut -d= -f2)"
echo "     curl -s -X POST http://localhost:8080/v1/cluster/review \\"
echo "       -H \"Authorization: Bearer $TOKEN" | python3 -m json.tool"
echo "     curl -s http://localhost:8080/v1/audit/recent \\"
echo "       -H \"Authorization: Bearer $TOKEN" | python3 -m json.tool"
echo ""
echo "   To stop:        scripts/stop.sh"
echo "   To pull model:  scripts/pull-model.sh"
