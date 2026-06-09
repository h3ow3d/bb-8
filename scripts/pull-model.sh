#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/deploy/compose/.env"
ENV_EXAMPLE="${REPO_ROOT}/deploy/compose/.env.example"
COMPOSE_FILE="${REPO_ROOT}/deploy/compose/docker-compose.yml"

echo "🤖 BB-8 Model Downloader"
echo "========================"

# Resolve model name from .env
if [ -f "${ENV_FILE}" ]; then
    OLLAMA_MODEL="$(grep "^OLLAMA_MODEL=" "${ENV_FILE}" | cut -d= -f2 || echo "")"
fi
if [ -z "${OLLAMA_MODEL:-}" ] && [ -f "${ENV_EXAMPLE}" ]; then
    OLLAMA_MODEL="$(grep "^OLLAMA_MODEL=" "${ENV_EXAMPLE}" | cut -d= -f2 || echo "")"
fi
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b-instruct}"

echo "Model to pull: ${OLLAMA_MODEL}"

# Start Ollama container if not already running
if ! docker ps --format '{{.Names}}' | grep -q "bb8-ollama"; then
    echo "Starting Ollama container..."
    docker compose -f "${COMPOSE_FILE}" up -d ollama
    echo "Waiting for Ollama to be ready..."
    sleep 5
fi

echo "Pulling model: ${OLLAMA_MODEL}"
echo "This may take several minutes for first-time download (~4-8 GB for 7B models)."
echo ""
docker exec bb8-ollama ollama pull "${OLLAMA_MODEL}"

echo ""
echo "✅ Model '${OLLAMA_MODEL}' is ready."
echo ""
echo "For air-gapped environments:"
echo "  1. Pull the model on a machine with internet access using this script."
echo "  2. Export the Ollama data volume:  docker run --rm -v bb8_ollama_data:/data -v \$(pwd):/backup alpine tar czf /backup/ollama-data.tar.gz -C /data ."
echo "  3. Transfer ollama-data.tar.gz to your air-gapped host."
echo "  4. Import on the air-gapped host:  docker run --rm -v bb8_ollama_data:/data -v \$(pwd):/backup alpine tar xzf /backup/ollama-data.tar.gz -C /data"
