#!/usr/bin/env bash
# Build the distributable WordPress plugin zip served at /woo-ai-manager.zip.
# Usage: ./scripts/build-plugin-zip.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/static/woo-ai-manager.zip"

cd "$REPO_ROOT"
rm -f "$OUT"
zip -r "$OUT" woo-ai-manager \
  -x "woo-ai-manager/.DS_Store" \
  -x "woo-ai-manager/**/.DS_Store"

echo "Built $OUT"
