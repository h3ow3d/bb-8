#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${1:-$(git -C "${REPO_ROOT}" describe --tags --exact-match 2>/dev/null || echo "dev")}"
BUNDLE_NAME="bb-8-mvp-${VERSION}"
BUNDLE_DIR="/tmp/${BUNDLE_NAME}"
BUNDLE_TAR="${REPO_ROOT}/${BUNDLE_NAME}.tar.gz"

echo "🏗  Preparing release bundle: ${BUNDLE_NAME}"

rm -rf "${BUNDLE_DIR}"
mkdir -p "${BUNDLE_DIR}"

# Copy files
cp "${REPO_ROOT}/README.md" "${BUNDLE_DIR}/"
cp -r "${REPO_ROOT}/deploy" "${BUNDLE_DIR}/"
cp -r "${REPO_ROOT}/scripts" "${BUNDLE_DIR}/"
cp -r "${REPO_ROOT}/docs" "${BUNDLE_DIR}/"

# Copy SBOM if present
find "${REPO_ROOT}" -maxdepth 1 -name "*.sbom.*" -exec cp {} "${BUNDLE_DIR}/" \; 2>/dev/null || true
find "${REPO_ROOT}" -maxdepth 1 -name "sbom*" -exec cp {} "${BUNDLE_DIR}/" \; 2>/dev/null || true

# Generate checksums
cd "${BUNDLE_DIR}"
find . -type f ! -name "checksums.txt" | sort | xargs sha256sum > checksums.txt
echo "Checksums written to checksums.txt"

# Create tarball
cd /tmp
tar czf "${BUNDLE_TAR}" "${BUNDLE_NAME}/"
echo ""
echo "✅ Bundle created: ${BUNDLE_TAR}"

# Cleanup
rm -rf "${BUNDLE_DIR}"
