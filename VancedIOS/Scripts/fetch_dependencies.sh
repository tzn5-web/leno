#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$ROOT/Config/dependencies.lock.json"
DEST="$ROOT/ThirdParty"

mkdir -p "$DEST"

clone_exact() {
  local name="$1" repo="$2" ref="$3" dest="$4"
  if [[ ! -d "$dest/.git" ]]; then
    rm -rf "$dest"
    git clone --quiet "$repo" "$dest"
  fi
  git -C "$dest" fetch --quiet origin "$ref"
  git -C "$dest" checkout --quiet --detach "$ref"
  git -C "$dest" submodule update --init --recursive --quiet
  local actual
  actual="$(git -C "$dest" rev-parse HEAD)"
  if [[ "$actual" != "$ref" ]]; then
    echo "DEPENDENCY_PIN_MISMATCH name=$name expected=$ref actual=$actual" >&2
    exit 21
  fi
  echo "PIN_OK name=$name ref=$actual"
}

while IFS=$'\t' read -r kind name remote ref; do
  case "$kind" in
    header) dest="$DEST/Headers/$name" ;;
    module) dest="$DEST/Modules/$name" ;;
    *) echo "UNKNOWN_KIND=$kind" >&2; exit 22 ;;
  esac
  mkdir -p "$(dirname "$dest")"
  clone_exact "$name" "$remote" "$ref" "$dest"
done < <(python3 - "$LOCK" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    d=json.load(f)
for item in d.get('headers', []):
    print('header', item['name'], item['repo'], item['ref'], sep='\t')
for item in d.get('modules', []):
    print('module', item['name'], item['repo'], item['ref'], sep='\t')
PY
)

echo "DEPENDENCY_FETCH_COMPLETE=1"
