#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT="${1:-}"

if [[ -n "$INPUT" ]]; then
  python3 "$ROOT/Scripts/audit.py" --ipa "$INPUT" --json-out "$ROOT/reports/PREBUILD_AUDIT.json" || true
fi

"$ROOT/Scripts/bootstrap_theos.sh"
export THEOS="$ROOT/.toolchain/theos"

make -C "$ROOT" clean all

DYLIB="$(find "$ROOT/.theos/obj" -type f -name 'VancedCore.dylib' -print | head -n 1)"
if [[ -z "$DYLIB" || ! -s "$DYLIB" ]]; then
  echo "VANCED_CORE_BUILD_MISSING" >&2
  exit 30
fi

if command -v file >/dev/null 2>&1; then
  DESC="$(file "$DYLIB")"
  echo "$DESC"
  echo "$DESC" | grep -q 'arm64' || { echo "VANCED_CORE_NOT_ARM64" >&2; exit 31; }
fi

mkdir -p "$ROOT/reports"
python3 - "$DYLIB" "$ROOT/reports/CORE_BUILD.json" <<'PY'
import hashlib, json, pathlib, sys
p=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
data=p.read_bytes()
out.write_text(json.dumps({
  'status':'PASS',
  'artifact':str(p),
  'size':len(data),
  'sha256':hashlib.sha256(data).hexdigest()
}, indent=2)+'\n', encoding='utf-8')
PY

echo "VANCED_CORE_BUILD=PASS"
echo "VANCED_CORE_DYLIB=$DYLIB"
