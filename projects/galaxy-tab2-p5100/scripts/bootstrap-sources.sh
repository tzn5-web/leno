#!/usr/bin/env bash
# Source-only checkout. Does not build or touch a device.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${1:-"$HOME/gt-p5100-legacy"}"
mkdir -p "$ROOT"
while IFS='|' read -r remote revision relpath; do
  target="$ROOT/$relpath"
  if [[ -e "$target" ]]; then
    echo "EXISTS=$target (not overwritten)"
    continue
  fi
  mkdir -p "$(dirname "$target")"
  git clone --quiet --no-checkout "https://github.com/$remote.git" "$target"
  git -C "$target" checkout --quiet --detach "$revision"
  echo "CHECKED_OUT=$relpath@$revision"
done < <(python3 - "$HERE/sources.lock.json" <<'PY'
import json,sys
for r in json.load(open(sys.argv[1],encoding="utf-8"))["repositories"]:
    print(f'{r["repo"]}|{r["revision"]}|{r["path"]}')
PY
)
python3 "$HERE/scripts/preflight.py" "$ROOT"
