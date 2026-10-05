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

head_matches() {
  local dst="$1"
  local expected="$2"
  [[ -d "$dst/.git" ]] || return 1
  [[ "$(git -C "$dst" rev-parse HEAD 2>/dev/null || true)" == "$expected" ]]
}

clone_at() {
  local name="$1"
  local dst="$2"
  local url commit
  url="$(dep "$name" repo)"
  commit="$(dep "$name" commit)"

  if head_matches "$dst" "$commit"; then
    echo "==> Reuse pinned $name @ $commit"
    return 0
  fi

  echo "==> Checkout pinned $name @ $commit"
  rm -rf "$dst"
  git init -q "$dst"
  git -C "$dst" remote add origin "$url"
  git -C "$dst" fetch -q --depth=1 origin "$commit"
  git -C "$dst" checkout -q --detach FETCH_HEAD

  local actual
  actual="$(git -C "$dst" rev-parse HEAD)"
  [[ "$actual" == "$commit" ]] || {
    echo "Pinned checkout mismatch for $name: expected $commit got $actual" >&2
    exit 1
  }
}

clone_sdk_at() {
  local dst="$1"
  local sdk_name="$2"
  local url commit
  url="$(dep iOSSDKs repo)"
  commit="$(dep iOSSDKs commit)"

  if head_matches "$dst" "$commit" && [[ -d "$dst/$sdk_name" ]]; then
    echo "==> Reuse pinned iOSSDKs @ $commit ($sdk_name)"
    return 0
  fi

  echo "==> Sparse checkout pinned iOSSDKs @ $commit ($sdk_name)"
  rm -rf "$dst"
  git init -q "$dst"
  git -C "$dst" remote add origin "$url"
  git -C "$dst" config core.sparseCheckout true
  printf "%s\n" "$sdk_name/" > "$dst/.git/info/sparse-checkout"
  git -C "$dst" fetch -q --depth=1 origin "$commit"
  git -C "$dst" checkout -q --detach FETCH_HEAD

  local actual
  actual="$(git -C "$dst" rev-parse HEAD)"
  [[ "$actual" == "$commit" && -d "$dst/$sdk_name" ]] || {
    echo "Pinned SDK checkout mismatch or SDK missing: $sdk_name @ $commit" >&2
    exit 1
  }
}

echo "==> Audit architecture"
python3 "$ROOT/VancedIOS/Scripts/audit.py"

clone_at Theos "$THEOS"
git -C "$THEOS" submodule update --init --recursive --depth=1
export THEOS

if command -v brew >/dev/null 2>&1; then
  GNU_MAKE_PREFIX="$(brew --prefix make 2>/dev/null || true)"
  if [[ -n "$GNU_MAKE_PREFIX" ]]; then
    export PATH="$GNU_MAKE_PREFIX/libexec/gnubin:$PATH"
  fi
fi

SDK_NAME="$(dep iOSSDKs sdk)"
SDK_REPO="$WORK/iOS-SDKs"
SDK_COMMIT="$(dep iOSSDKs commit)"
SDK_MARKER="$THEOS/sdks/.vancedios-${SDK_NAME}.commit"

clone_sdk_at "$SDK_REPO" "$SDK_NAME"
mkdir -p "$THEOS/sdks"

INSTALLED_SDK_COMMIT=""
if [[ -f "$SDK_MARKER" ]]; then
  INSTALLED_SDK_COMMIT="$(cat "$SDK_MARKER")"
fi
if [[ ! -d "$THEOS/sdks/$SDK_NAME" || "$INSTALLED_SDK_COMMIT" != "$SDK_COMMIT" ]]; then
  echo "==> Install pinned iOS SDK: $SDK_NAME @ $SDK_COMMIT"
  rm -rf "$THEOS/sdks/$SDK_NAME"
  cp -R "$SDK_REPO/$SDK_NAME" "$THEOS/sdks/$SDK_NAME"
  printf "%s\n" "$SDK_COMMIT" > "$SDK_MARKER"
else
  echo "==> Reuse pinned iOS SDK: $SDK_NAME @ $SDK_COMMIT"
fi

echo "==> Install pinned headers"
clone_at YouTubeHeader "$THEOS/include/YouTubeHeader"
clone_at PSHeader "$THEOS/include/PSHeader"

echo "==> Clone pinned patch modules"
clone_at YouMod "$WORK/YouMod"
clone_at YTVideoOverlay "$WORK/YTVideoOverlay"
clone_at YouPiP "$WORK/YouPiP"
clone_at YTUHD "$WORK/YTUHD"
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
    rm -rf packages
    make package DEBUG=0 FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=rootless "$@"
  )

  local count pkg
  count="$(find "$dir/packages" -type f -name '*.deb' 2>/dev/null | wc -l | tr -d '[:space:]')"
  [[ "$count" == "1" ]] || {
    echo "Expected exactly one package from $dir, found $count" >&2
    find "$dir/packages" -type f -name '*.deb' -print 2>/dev/null || true
    exit 1
  }

  pkg="$(find "$dir/packages" -type f -name '*.deb' -print -quit)"
  [[ -n "$pkg" && -f "$pkg" ]] || {
    echo "Package missing after build: $dir" >&2
    exit 1
  }
  cp "$pkg" "$DIST/$out"
}

build_deb "$WORK/YouMod" "youmod.deb"
build_deb "$WORK/YTVideoOverlay" "ytvideooverlay.deb"
build_deb "$WORK/YouPiP" "youpip.deb"
build_deb "$WORK/YTUHD" "ytuhd.deb"
build_deb "$WORK/Return-YouTube-Dislikes" "return-youtube-dislikes.deb"
build_deb "$ROOT/VancedIOS/Core" "vancedios-core.deb"

python3 - "$DIST" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
packages = sorted(root.glob("*.deb"))
if len(packages) != 6:
    raise SystemExit(f"expected 6 VancedIOS packages, got {len(packages)}")
for p in packages:
    print(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
PY
