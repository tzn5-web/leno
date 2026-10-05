#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 /path/to/decrypted-YouTube.ipa /path/to/output.ipa [bundle-id] [display-name]" >&2
  exit 2
fi

BASE_IPA="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT="$2"
BUNDLE_ID="${3:-com.google.ios.youtube}"
DISPLAY_NAME="${4:-YouTube}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="${VANCEDIOS_DIST:-$ROOT/dist/vanced-ios}"

python3 "$ROOT/VancedIOS/Scripts/audit.py"

for f in youmod.deb youpip.deb return-youtube-dislikes.deb vancedios-core.deb; do
  test -f "$DIST/$f" || {
    echo "Missing $DIST/$f. Run build_patches.sh first." >&2
    exit 1
  }
done

python3 - "$BASE_IPA" <<'PY'
import plistlib, sys, zipfile
p = sys.argv[1]
with zipfile.ZipFile(p) as z:
    app_roots = sorted({n.split("/Info.plist")[0] + "/" for n in z.namelist() if n.startswith("Payload/") and n.endswith(".app/Info.plist")})
    if not app_roots:
        raise SystemExit("IPA does not contain Payload/*.app/Info.plist")
    app = app_roots[0]
    info = plistlib.loads(z.read(app + "Info.plist"))
    name = info.get("CFBundleDisplayName") or info.get("CFBundleName")
    bid = info.get("CFBundleIdentifier")
    ver = info.get("CFBundleShortVersionString")
    print(f"Host: {name} {ver} ({bid})")
PY

command -v cyan >/dev/null || {
  echo "cyan not found. Install the pinned pyzule-rw/cyan tool first." >&2
  exit 1
}

cyan -i "$BASE_IPA" -o "$OUTPUT" -uwef \
  "$DIST/youmod.deb" \
  "$DIST/youpip.deb" \
  "$DIST/return-youtube-dislikes.deb" \
  "$DIST/vancedios-core.deb" \
  -b "$BUNDLE_ID" \
  -n "$DISPLAY_NAME"

python3 - "$OUTPUT" <<'PY'
import plistlib, sys, zipfile
p = sys.argv[1]
with zipfile.ZipFile(p) as z:
    app_roots = sorted({n.split("/Info.plist")[0] + "/" for n in z.namelist() if n.startswith("Payload/") and n.endswith(".app/Info.plist")})
    if not app_roots:
        raise SystemExit("Output IPA missing Payload/*.app/Info.plist")
    app = app_roots[0]
    info = plistlib.loads(z.read(app + "Info.plist"))
    names = [n.lower() for n in z.namelist()]
    groups = {
        "YouMod": ("youmod",),
        "YouPiP": ("youpip",),
        "ReturnYouTubeDislikes": ("youtubedislikes", "return-youtube-dislikes", "ryd"),
        "VancedIOSCore": ("vancedioscore",),
    }
    missing=[]
    for label, needles in groups.items():
        if not any(any(needle in name for needle in needles) for name in names):
            missing.append(label)
    if missing:
        raise SystemExit("Injected payload missing: " + ", ".join(missing))
    print("Output bundle:", info.get("CFBundleIdentifier"))
    print("Output name:", info.get("CFBundleDisplayName") or info.get("CFBundleName"))
    print("Injected tweak layers: OK")
PY
