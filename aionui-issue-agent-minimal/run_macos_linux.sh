#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AionUi Issue Agent (macOS/Linux) - v22
# - Thin wrapper: delegate to python bootstrap
# ============================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" "$ROOT/scripts/python/bootstrap.py" "$@"
