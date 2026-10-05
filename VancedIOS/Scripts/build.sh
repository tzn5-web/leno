#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT="${1:-}"
REPORTS="$ROOT/reports"
mkdir -p "$REPORTS"

bash "$ROOT/Scripts/bootstrap_theos.sh"
export THEOS="$ROOT/.toolchain/theos"

if [[ -z "$INPUT" ]]; then
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

  python3 - "$DYLIB" "$REPORTS/CORE_BUILD.json" <<'PY'
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
  exit 0
fi

INPUT="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
[[ -e "$INPUT" ]] || { echo "INPUT_NOT_FOUND=$INPUT" >&2; exit 32; }

python3 "$ROOT/Scripts/audit.py" \
  --ipa-only \
  --ipa "$INPUT" \
  --json-out "$REPORTS/PREBUILD_IPA_AUDIT.json"

rm -rf "$ROOT/packages" "$ROOT/.theos" "$ROOT/tmp"

make -C "$ROOT" clean package \
  PACKAGE_IPA=1 \
  IPA="$INPUT" \
  THEOS_PACKAGE_SCHEME=rootless \
  FINALPACKAGE=1

OUTPUT="$(find "$ROOT/packages" -maxdepth 1 -type f -name '*.ipa' -print | sort | tail -n 1)"
if [[ -z "$OUTPUT" || ! -s "$OUTPUT" ]]; then
  echo "PACKAGED_IPA_MISSING" >&2
  find "$ROOT/packages" -maxdepth 2 -type f -print 2>/dev/null || true
  exit 33
fi

python3 "$ROOT/Scripts/audit.py" \
  --ipa-only \
  --built-ipa "$OUTPUT" \
  --json-out "$REPORTS/POSTBUILD_IPA_AUDIT.json"

python3 - "$INPUT" "$OUTPUT" "$REPORTS/PACKAGE_BUILD.json" <<'PY'
import hashlib, json, pathlib, plistlib, sys, zipfile

src=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
report=pathlib.Path(sys.argv[3])

def info_from_ipa(path):
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.startswith("Payload/") and n.count("/") == 2 and n.endswith(".app/Info.plist")]
        if len(names) != 1:
            raise SystemExit(f"expected exactly one app Info.plist in {path}, found {len(names)}")
        return plistlib.loads(z.read(names[0]))

src_info=info_from_ipa(src)
out_info=info_from_ipa(out)
keys=["CFBundleIdentifier","CFBundleShortVersionString","CFBundleVersion","CFBundleExecutable","UIBackgroundModes"]
changes={}
for key in keys:
    before=src_info.get(key)
    after=out_info.get(key)
    if before != after:
        changes[key]={"input":before,"output":after}

data=out.read_bytes()
result={
  "status":"PASS" if not changes else "FAIL",
  "input":str(src),
  "output":str(out),
  "output_size":len(data),
  "output_sha256":hashlib.sha256(data).hexdigest(),
  "identity_changes":changes,
}
report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if changes:
    raise SystemExit(f"packaged IPA changed protected identity fields: {changes}")
PY

echo "VANCED_IPA_PACKAGE=PASS"
echo "OUTPUT_IPA=$OUTPUT"
if command -v shasum >/dev/null 2>&1; then
  echo "SHA256=$(shasum -a 256 "$OUTPUT" | awk '{print $1}')"
else
  echo "SHA256=$(sha256sum "$OUTPUT" | awk '{print $1}')"
fi
