#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 /path/to/decrypted-YouTube.ipa /path/to/output.ipa [bundle-id] [display-name]" >&2
  exit 2
fi

BASE_IPA="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_DIR="$(cd "$(dirname "$2")" && pwd)"
OUTPUT="$OUTPUT_DIR/$(basename "$2")"
BUNDLE_ID="${3:-com.google.ios.youtube}"
DISPLAY_NAME="${4:-YouTube}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/VancedIOS/manifest.json"
DIST="${VANCEDIOS_DIST:-$ROOT/dist/vanced-ios}"
VALIDATOR="$ROOT/VancedIOS/Scripts/validate_ipa.py"

[[ "$BASE_IPA" != "$OUTPUT" ]] || {
  echo "Input and output IPA paths must be different." >&2
  exit 2
}

TESTED_VERSION="$(
  python3 - "$MANIFEST" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    print(json.load(f)["target"]["tested_youtube_version"])
PY
)"
echo "VancedIOS tested_youtube_version=$TESTED_VERSION"

python3 "$ROOT/VancedIOS/Scripts/audit.py"

for f in youmod.deb ytvideooverlay.deb youpip.deb ytuhd.deb return-youtube-dislikes.deb vancedios-core.deb; do
  [[ -f "$DIST/$f" ]] || {
    echo "Missing $DIST/$f. Run build_patches.sh first." >&2
    exit 1
  }
done

# Strict preflight: official host bundle, exact tested version, arm64,
# UIBackgroundModes audio, and decrypted App Store Mach-O (cryptid == 0).
python3 "$VALIDATOR" host "$BASE_IPA" --manifest "$MANIFEST"

command -v cyan >/dev/null 2>&1 || {
  echo "cyan not found. Install the manifest-pinned pyzule-rw/cyan revision first." >&2
  exit 1
}

rm -f "$OUTPUT"
cleanup_failed_output() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    rm -f "$OUTPUT"
  fi
  exit "$rc"
}
trap cleanup_failed_output EXIT

cyan -i "$BASE_IPA" -o "$OUTPUT" -uwef   "$DIST/youmod.deb"   "$DIST/ytvideooverlay.deb"   "$DIST/youpip.deb"   "$DIST/ytuhd.deb"   "$DIST/return-youtube-dislikes.deb"   "$DIST/vancedios-core.deb"   -b "$BUNDLE_ID"   -n "$DISPLAY_NAME"

[[ -s "$OUTPUT" ]] || {
  echo "cyan returned without producing a non-empty output IPA." >&2
  exit 1
}

# Strict postflight verifies exact injected dylibs and LC_LOAD_DYLIB entries.
python3 "$VALIDATOR" output "$OUTPUT"   --manifest "$MANIFEST"   --bundle-id "$BUNDLE_ID"   --display-name "$DISPLAY_NAME"

trap - EXIT
echo "VancedIOS injection: PASS"
