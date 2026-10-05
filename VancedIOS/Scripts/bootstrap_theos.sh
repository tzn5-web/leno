#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$ROOT/Config/dependencies.lock.json"
TOOLCHAIN="$ROOT/.toolchain"
THEOS="$TOOLCHAIN/theos"

mkdir -p "$TOOLCHAIN"

readarray -t fields < <(python3 - "$LOCK" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    d=json.load(f)['theos']
print(d['repo'])
print(d['ref'])
PY
)

REPO="${fields[0]}"
REF="${fields[1]}"

if [[ ! -d "$THEOS/.git" ]]; then
  rm -rf "$THEOS"
  git clone --quiet --recursive "$REPO" "$THEOS"
fi

git -C "$THEOS" fetch --quiet origin "$REF"
git -C "$THEOS" checkout --quiet --detach "$REF"
git -C "$THEOS" submodule update --init --recursive --quiet

ACTUAL="$(git -C "$THEOS" rev-parse HEAD)"
if [[ "$ACTUAL" != "$REF" ]]; then
  echo "THEOS_PIN_MISMATCH expected=$REF actual=$ACTUAL" >&2
  exit 20
fi

echo "THEOS=$THEOS"
echo "THEOS_REF=$ACTUAL"
