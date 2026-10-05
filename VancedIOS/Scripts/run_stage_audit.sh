#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/reports"

python3 "$ROOT/Scripts/audit.py" --json-out "$ROOT/reports/STAGE_AUDIT.json" "$@"
