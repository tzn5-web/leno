#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPORTS="$ROOT/reports"
INPUT="${1:-}"
mkdir -p "$REPORTS"
rm -f "$REPORTS/STAGE_AUDIT.json" "$REPORTS/CORE_BUILD.json" \
      "$REPORTS/PREBUILD_IPA_AUDIT.json" "$REPORTS/POSTBUILD_IPA_AUDIT.json" \
      "$REPORTS/PACKAGE_BUILD.json" "$REPORTS/FINAL_REPORT.json"

stage_rc=0
build_rc=0

echo "[1/3] Source + product stage audit"
python3 "$ROOT/Scripts/audit.py" --json-out "$REPORTS/STAGE_AUDIT.json" || stage_rc=$?

echo "[2/3] Core build${INPUT:+ + IPA package}"
if [[ -n "$INPUT" ]]; then
  bash "$ROOT/Scripts/build.sh" "$INPUT" || build_rc=$?
else
  bash "$ROOT/Scripts/build.sh" || build_rc=$?
fi

echo "[3/3] Final report"
python3 - "$REPORTS" "$stage_rc" "$build_rc" <<'PY'
import json, pathlib, sys
reports=pathlib.Path(sys.argv[1])
stage_rc=int(sys.argv[2])
build_rc=int(sys.argv[3])

def read(name):
    path=reports/name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'status':'INVALID_REPORT','error':str(exc),'path':str(path)}

result={
  'stage_rc':stage_rc,
  'build_rc':build_rc,
  'input_ipa_supplied': bool(read('PREBUILD_IPA_AUDIT.json')),
  'input_ipa_required_for_final_validation': not bool(read('PREBUILD_IPA_AUDIT.json')),
  'product_stage':read('STAGE_AUDIT.json'),
  'core_build':read('CORE_BUILD.json'),
  'prebuild_ipa':read('PREBUILD_IPA_AUDIT.json'),
  'postbuild_ipa':read('POSTBUILD_IPA_AUDIT.json'),
  'package_build':read('PACKAGE_BUILD.json'),
}
result['status']='PASS' if stage_rc == 0 and build_rc == 0 else 'NEEDS_REVIEW'
(reports/'FINAL_REPORT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2,sort_keys=True))
PY

echo "FINAL_REPORT=$REPORTS/FINAL_REPORT.json"
if [[ -z "$INPUT" ]]; then
  echo "INPUT_IPA_REQUIRED=1"
  echo "NEXT_COMMAND=$ROOT/RUNNER.sh /path/to/YouTube.ipa"
fi
if [[ "$build_rc" -ne 0 ]]; then
  exit "$build_rc"
fi
if [[ "$stage_rc" -ne 0 ]]; then
  exit 2
fi
exit 0
