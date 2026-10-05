#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/VancedIOS/manifest.json"
WORK="${VANCEDIOS_WORK:-$ROOT/.vancedios-build}"
DIST="${VANCEDIOS_DIST:-$ROOT/dist/vanced-ios}"
THEOS="${THEOS:-$WORK/theos}"

mkdir -p "$WORK" "$DIST"
rm -rf "$DIST"/*

dep() {
  python3 - "$MANIFEST" "$1" "$2" <<'PY'
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
print(data["dependencies"][sys.argv[2]][sys.argv[3]])
PY
}

clone_at() {
  local name="$1"
  local dst="$2"
  local url commit
  url="$(dep "$name" repo)"
  commit="$(dep "$name" commit)"
  rm -rf "$dst"
  git init -q "$dst"
  git -C "$dst" remote add origin "$url"
  git -C "$dst" fetch -q --depth=1 origin "$commit"
  git -C "$dst" checkout -q --detach FETCH_HEAD
}

echo "==> Audit architecture"
python3 "$ROOT/VancedIOS/Scripts/audit.py"

if [[ ! -d "$THEOS/.git" ]]; then
  echo "==> Setup pinned Theos"
  clone_at Theos "$THEOS"
  git -C "$THEOS" submodule update --init --recursive --depth=1
fi

export THEOS
if command -v brew >/dev/null 2>&1; then
  GNU_MAKE_PREFIX="$(brew --prefix make 2>/dev/null || true)"
  if [[ -n "$GNU_MAKE_PREFIX" ]]; then
    export PATH="$GNU_MAKE_PREFIX/libexec/gnubin:$PATH"
  fi
fi

SDK_NAME="$(dep iOSSDKs sdk)"
if [[ ! -d "$THEOS/sdks/$SDK_NAME" ]]; then
  echo "==> Install pinned iOS SDK: $SDK_NAME"
  SDK_REPO="$WORK/iOS-SDKs"
  SDK_URL="$(dep iOSSDKs repo)"
  SDK_COMMIT="$(dep iOSSDKs commit)"
  rm -rf "$SDK_REPO"
  git init -q "$SDK_REPO"
  git -C "$SDK_REPO" remote add origin "$SDK_URL"
  git -C "$SDK_REPO" config core.sparseCheckout true
  printf "%s\n" "$SDK_NAME" > "$SDK_REPO/.git/info/sparse-checkout"
  git -C "$SDK_REPO" fetch -q --depth=1 origin "$SDK_COMMIT"
  git -C "$SDK_REPO" checkout -q --detach FETCH_HEAD
  mkdir -p "$THEOS/sdks"
  cp -R "$SDK_REPO/$SDK_NAME" "$THEOS/sdks/$SDK_NAME"
fi

echo "==> Install pinned headers"
clone_at YouTubeHeader "$THEOS/include/YouTubeHeader"
clone_at PSHeader "$THEOS/include/PSHeader"

echo "==> Clone pinned patch modules"
clone_at YouMod "$WORK/YouMod"
clone_at YTVideoOverlay "$WORK/YTVideoOverlay"
clone_at YouPiP "$WORK/YouPiP"
clone_at ReturnYouTubeDislikes "$WORK/Return-YouTube-Dislikes"

echo "==> Audit pinned patch contracts"
python3 "$ROOT/VancedIOS/Scripts/audit_patches.py" "$WORK"

build_deb() {
  local dir="$1"
  local out="$2"
  shift 2
  echo "==> Build $out"
  (
    cd "$dir"
    make clean >/dev/null 2>&1 || true
    make package DEBUG=0 FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=rootless "$@"
  )
  local pkg
  pkg="$(find "$dir/packages" -type f -name '*.deb' | sort | tail -n1)"
  test -n "$pkg" -a -f "$pkg"
  cp "$pkg" "$DIST/$out"
}

build_deb "$WORK/YouMod" "youmod.deb"
build_deb "$WORK/YouPiP" "youpip.deb"
build_deb "$WORK/Return-YouTube-Dislikes" "return-youtube-dislikes.deb"
build_deb "$ROOT/VancedIOS/Core" "vancedios-core.deb"

python3 - "$DIST" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
for p in sorted(root.glob("*.deb")):
    print(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
PY
