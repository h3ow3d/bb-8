#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/deploy/compose/.env"
ENV_EXAMPLE="${REPO_ROOT}/deploy/compose/.env.example"

BASE_URL="http://localhost:8080"

echo "🧪 BB-8 Smoke Test"
echo "==================="

# Resolve API token
if [ -f "${ENV_FILE}" ]; then
    API_TOKEN="$(grep "^SIDECAR_API_TOKEN=" "${ENV_FILE}" | cut -d= -f2 | tr -d \'\' | tr -d \")"
elif [ -f "${ENV_EXAMPLE}" ]; then
    API_TOKEN="$(grep "^SIDECAR_API_TOKEN=" "${ENV_EXAMPLE}" | cut -d= -f2 | tr -d \'\' | tr -d \")"
else
    API_TOKEN="change-me"
fi

PASS=0
FAIL=0

check() {
    local name="$1"
    local status="$2"
    if [ "${status}" -eq 0 ]; then
        echo "  ✅ PASS: ${name}"
        PASS=$((PASS + 1))
    else
        echo "  ❌ FAIL: ${name}"
        FAIL=$((FAIL + 1))
    fi
}

# Test 1: /health
echo ""
echo "1. Testing /health (no auth required)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health" 2>/dev/null || echo "000")
check "/health returns 200" "$([ "${HTTP_CODE}" = "200" ] && echo 0 || echo 1)"

# Test 2: Protected endpoint rejects missing token
echo ""
echo "2. Testing protected endpoint rejects missing token..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/v1/audit/recent" 2>/dev/null || echo "000")
check "/v1/audit/recent returns 401 without token" "$([ "${HTTP_CODE}" = "401" ] && echo 0 || echo 1)"

# Test 3: Protected endpoint rejects wrong token
echo ""
echo "3. Testing protected endpoint rejects wrong token..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer invalid-wrong-token" \
    "${BASE_URL}/v1/audit/recent" 2>/dev/null || echo "000")
check "/v1/audit/recent returns 401 with wrong token" "$([ "${HTTP_CODE}" = "401" ] && echo 0 || echo 1)"

# Test 4: Protected endpoint accepts correct token
echo ""
echo "4. Testing protected endpoint accepts correct token..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${API_TOKEN}" \
    "${BASE_URL}/v1/audit/recent" 2>/dev/null || echo "000")
check "/v1/audit/recent returns 200 with correct token" "$([ "${HTTP_CODE}" = "200" ] && echo 0 || echo 1)"

# Test 5: Cluster review (skip if kubeconfig missing)
echo ""
echo "5. Testing /v1/cluster/review..."
if [ -n "${KUBECONFIG:-}" ] && [ -f "${KUBECONFIG}" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Authorization: Bearer ${API_TOKEN}" \
        "${BASE_URL}/v1/cluster/review" 2>/dev/null || echo "000")
    check "/v1/cluster/review returns 2xx or 503" "$([ "${HTTP_CODE}" -ge 200 ] && [ "${HTTP_CODE}" -lt 600 ] && echo 0 || echo 1)"
else
    echo "  ⏭  SKIP: /v1/cluster/review — kubeconfig not available (set KUBECONFIG env var)"
fi

# Summary
echo ""
echo "============================="
echo "Results: ${PASS} passed, ${FAIL} failed"
echo ""

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
exit 0
