#!/usr/bin/env bash
# K2401 existing Azure Linux VM: frozen sources, no invented UI or vehicle images.
set -Eeuo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
ROOT=/opt/k2401-evo-workspace
REPORT="$ROOT/reports"
mkdir -p "$REPORT" "$ROOT/original-immutable" "$ROOT/generated" "$ROOT/tools"
exec 3>&1
exec > >(tee -a "$REPORT/azure-setup.log" >&3) 2>&1
trap 'code=$?; echo "K2401_VM_RUN_EXIT=$code"; if test "$code" -ne 0; then tail -n 60 "$REPORT/azure-setup.log" >&3 || true; fi' EXIT
EXPECTED_SHA=""
BLOB_SAS_B64=""
# Azure RunShellScript may inject named parameters as variables rather than
# positional arguments. Accept BOTH documented forms; never continue without
# the immutable SHA.
if test -n "${ExpectedSha:-}"; then EXPECTED_SHA="${ExpectedSha}"; fi
if test -n "${BlobSasB64:-}"; then BLOB_SAS_B64="${BlobSasB64}"; fi
for arg in "$@"; do
  case "$arg" in
    ExpectedSha=*) EXPECTED_SHA="$(printf '%s' "$arg" | cut -d = -f 2)";;
    BlobSasB64=*) BLOB_SAS_B64="$(printf '%s' "$arg" | cut -d = -f 2-)";;
  esac
done
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR=INVALID_EXPECTED_SHA'; exit 2; }
date -u --iso-8601=seconds > "$REPORT/started-utc.txt"
echo "K2401_FROZEN_SHA=$EXPECTED_SHA"
apt-get update -qq
apt-get install -y -qq git ca-certificates curl unzip zip jq openjdk-17-jdk-headless \
  python3 python3-pip python3-venv python3-dev build-essential libgl1 \
  imagemagick libvips-tools ffmpeg librsvg2-bin fonts-dejavu-core \
  libglu1-mesa libpulse0 libnss3 libx11-6 libxext6 libxrender1 >/dev/null
python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/python" -m pip install -q --upgrade pip
"$ROOT/venv/bin/python" -m pip install -q 'Pillow==11.3.0' 'opencv-contrib-python-headless==4.10.0.84' 'numpy==1.26.4'
"$ROOT/venv/bin/python" - <<'PY'
from PIL import Image
import cv2,numpy
assert hasattr(cv2,'dnn_superres')
print('K2401_SOFTWARE=PASS Pillow='+Image.__version__+' OpenCV='+cv2.__version__+' NumPy='+numpy.__version__)
PY
mkdir -p "$ROOT/git"
if [ ! -d "$ROOT/git/leno/.git" ]; then git clone --no-checkout https://github.com/tzn5-web/leno.git "$ROOT/git/leno"; fi
cd "$ROOT/git/leno"
git fetch --depth 1 origin "$EXPECTED_SHA"
git checkout --force --detach "$EXPECTED_SHA"
test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"
git status --porcelain > "$REPORT/initial-git-status.txt"
SCRIPT=projects/k2401-evo-launcher
ORIGINAL="$SCRIPT/app/src/main/assets/skins"
for i in $(seq -w 0 20); do
  test -s "$ORIGINAL/skin_$i.webp" || { echo "ERROR=MISSING_APPROVED_ORIGINAL_$i"; exit 3; }
done
( cd "$ORIGINAL" && sha256sum skin_??.webp | sort ) > "$REPORT/approved-originals-sha256.txt"
cp -a "$ORIGINAL"/skin_??.webp "$ROOT/original-immutable/"
chmod -R a-w "$ROOT/original-immutable"
"$ROOT/venv/bin/python" "$SCRIPT/scripts/verify-native-layout.py" | tee "$REPORT/layout-agent.txt"
K2401_REQUIRE_SR=YES "$ROOT/venv/bin/python" "$SCRIPT/scripts/build-uhd-skins.py" | tee "$REPORT/image-agent.txt"
K2401_REQUIRE_SR=YES "$ROOT/venv/bin/python" "$SCRIPT/scripts/build-clean-scenes.py" | tee "$REPORT/photo-agent.txt"
( cd "$ORIGINAL" && sha256sum skin_??.webp | sort ) > "$REPORT/approved-originals-sha256-after.txt"
cmp "$REPORT/approved-originals-sha256.txt" "$REPORT/approved-originals-sha256-after.txt" || { echo 'ERROR=APPROVED_ORIGINALS_MODIFIED'; exit 4; }
mkdir -p "$ROOT/generated/clean" "$ROOT/generated/uhd"
cp "$ORIGINAL"/clean/skin_??.webp "$ROOT/generated/clean/"
cp "$ORIGINAL"/uhd/skin_??.webp "$ROOT/generated/uhd/"
"$ROOT/venv/bin/python" - <<'PY' | tee "$REPORT/image-asset-qa.txt"
from pathlib import Path
from PIL import Image
root=Path('/opt/k2401-evo-workspace/generated')
for kind in ['clean','uhd']:
 files=sorted((root/kind).glob('skin_??.webp'))
 assert len(files)==21,(kind,len(files))
 for f in files:
  with Image.open(f) as img:
   assert img.size==(2560,1440),(f,img.size)
 print('K2401_21_'+kind.upper()+'_UHD_IMAGES=PASS')
print('K2401_21_APPROVED_ORIGINALS_IMMUTABLE=PASS')
PY
# Provide full 4K (3840x2160) restoration candidates separately from the
# 2560x1440 artwork used in the actual 1280x720 Android launcher.
# No car identity or new scenery is generated; only source-preserving resampling.
mkdir -p "$ROOT/generated/draft_4k"
"$ROOT/venv/bin/python" - <<'PY'
from pathlib import Path
from PIL import Image,ImageFilter
base=Path("/opt/k2401-evo-workspace/generated")
for i in range(21):
 source=base/"clean"/f"skin_{i:02}.webp"
 target=base/"draft_4k"/f"skin_{i:02}.webp"
 with Image.open(source) as im:
  image=im.convert("RGB").resize((3840,2160),Image.Resampling.LANCZOS)
  image=image.filter(ImageFilter.UnsharpMask(radius=1.08,percent=125,threshold=3))
  image.save(target,"WEBP",quality=96,method=6)
  assert image.size==(3840,2160)
print("K2401_21_SEPARATE_4K_IMAGE_CANDIDATES=PASS")
PY
( cd "$ROOT/generated" && sha256sum clean/skin_??.webp uhd/skin_??.webp draft_4k/skin_??.webp | sort ) > "$REPORT/uhd-asset-sha256.txt"
tar -C "$ROOT" -czf "$ROOT/k2401-locked-originals.tar.gz" original-immutable reports/approved-originals-sha256.txt
tar -C "$ROOT" -czf "$ROOT/k2401-21-uhd-assets.tar.gz" generated reports/uhd-asset-sha256.txt
du -h "$ROOT"/*.tar.gz | tee "$REPORT/archive-sizes.txt"
# Publish source backups and all 63 derived 2K/4K images BEFORE Gradle so an
# Android compilation error never loses the source-preserving artwork.
if [ -n "$BLOB_SAS_B64" ]; then
  PRIVATE_URL="$(printf '%s' "$BLOB_SAS_B64" | base64 -d)"
  case "$PRIVATE_URL" in
    https://tzn5androidartifacts26.blob.core.windows.net/k2401-evo-private\?*) ;;
    *) echo 'ERROR=UNEXPECTED_PRIVATE_STORAGE_URL'; exit 8;;
  esac
  BASE="$(printf '%s' "$PRIVATE_URL" | cut -d '?' -f 1)"
  QUERY="$(printf '%s' "$PRIVATE_URL" | cut -d '?' -f 2-)"
  UPLOAD_FOLDER="frozen-$(git rev-parse --short=12 HEAD)"
  for f in "$ROOT/k2401-locked-originals.tar.gz" "$ROOT/k2401-21-uhd-assets.tar.gz" \
      "$REPORT/approved-originals-sha256.txt" "$REPORT/uhd-asset-sha256.txt" \
      "$REPORT/image-asset-qa.txt" "$REPORT/layout-agent.txt"; do
    name="$(basename "$f")"
    curl -fsSL --retry 3 --max-time 300 -X PUT \
      -H 'x-ms-blob-type: BlockBlob' -H 'x-ms-version: 2020-10-02' \
      -H 'Content-Type: application/octet-stream' --upload-file "$f" \
      "$BASE/$UPLOAD_FOLDER/$name?$QUERY" >/dev/null
    echo "K2401_PRIVATE_AZURE_ASSET_SAVED=$name"
  done
fi
# Android SDK and Gradle stay installed on the existing VM disk between runs.
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME="$ROOT/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ROOT/venv/bin:$JAVA_HOME/bin:$PATH"
# Gradle invokes python3 for generateUhdSkins; use the same pinned virtualenv
# that already passed Pillow/OpenCV model reconstruction and integrity QA.
python3 -c "from PIL import Image; import cv2; print('K2401_AZURE_GRADLE_PYTHON_VENV=PASS')"
mkdir -p "$ANDROID_HOME/cmdline-tools"
if [ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]; then
  curl -fsSL --retry 3 --max-time 240 \
    https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip \
    -o "$ROOT/tools/android-commandline-tools.zip"
  mkdir -p "$ROOT/tools/sdk-extracted"
  unzip -oq "$ROOT/tools/android-commandline-tools.zip" -d "$ROOT/tools/sdk-extracted"
  mv "$ROOT/tools/sdk-extracted/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
fi
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
(yes | "$SDKMANAGER" --sdk_root="$ANDROID_HOME" --licenses >/dev/null 2>&1) || true
"$SDKMANAGER" --sdk_root="$ANDROID_HOME" 'platforms;android-35' \
  'build-tools;35.0.0' 'platform-tools' 'emulator' \
  'system-images;android-29;google_apis;x86_64' > "$REPORT/android-sdk-install.log" 2>&1
if [ ! -x "$ROOT/tools/gradle-8.11.1/bin/gradle" ]; then
  curl -fsSL --retry 3 --max-time 240 \
    https://services.gradle.org/distributions/gradle-8.11.1-bin.zip \
    -o "$ROOT/tools/gradle-8.11.1-bin.zip"
  unzip -oq "$ROOT/tools/gradle-8.11.1-bin.zip" -d "$ROOT/tools"
fi
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$SCRIPT/local.properties"
# Gradle invokes python3 directly; point that name to the verified venv.
export PATH="$ROOT/venv/bin:$PATH"
"$ROOT/tools/gradle-8.11.1/bin/gradle" --no-daemon -p "$SCRIPT" :app:assembleDebug \
  > "$REPORT/android-build.log" 2>&1 || {
    tail -n 90 "$REPORT/android-build.log"
    echo 'K2401_AZURE_ANDROID_COMPILE=FAIL'
    exit 7
  }
APK="$SCRIPT/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
sha256sum "$APK" > "$REPORT/azure-android-debug-apk-sha256.txt"
cp "$APK" "$ROOT/k2401-audited-debug-not-release.apk"
echo 'K2401_AZURE_ANDROID_COMPILE=PASS'
echo "K2401_IMAGE_TOOLS_INSTALLED=$(command -v convert) $(command -v vips) $(command -v ffmpeg)"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
AVD_NAME=k2401_api29_azure
if [ ! -f "$HOME/.android/avd/$AVD_NAME.ini" ]; then
  mkdir -p "$HOME/.android"
  printf 'no\n' | avdmanager create avd --force --name "$AVD_NAME" \
    --package 'system-images;android-29;google_apis;x86_64' \
    --device 'pixel_2' > "$REPORT/avd-create.log" 2>&1
fi
if [ -e /dev/kvm ] && [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
  ACCEL=on
else
  ACCEL=off
fi
echo "K2401_AZURE_EMULATOR_ACCEL=$ACCEL"
emulator -avd "$AVD_NAME" -no-window -no-boot-anim -no-audio \
  -no-snapshot -gpu swiftshader_indirect -accel "$ACCEL" \
  -memory 3072 -partition-size 2048 \
  > "$REPORT/emulator-boot.log" 2>&1 &
EMU_PID=$!
READY=NO
for j in $(seq 1 90); do
  if timeout 4 adb wait-for-device >/dev/null 2>&1 &&
     [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = 1 ]; then
    READY=YES
    break
  fi
  sleep 4
done
if [ "$READY" != YES ]; then
  echo 'K2401_AZURE_ANDROID10_EMULATOR_BOOT=FAIL'
  tail -n 80 "$REPORT/emulator-boot.log"
  kill "$EMU_PID" >/dev/null 2>&1 || true
  exit 10
fi
echo 'K2401_AZURE_ANDROID10_EMULATOR_BOOT=PASS'
timeout 900 bash "$SCRIPT/scripts/emulator-smoke.sh" \
  > "$REPORT/azure-android-emulator-smoke.log" 2>&1 || {
    tail -n 130 "$REPORT/azure-android-emulator-smoke.log"
    kill "$EMU_PID" >/dev/null 2>&1 || true
    echo 'K2401_AZURE_21_SKIN_EMULATOR_SMOKE=FAIL'
    exit 11
  }
echo 'K2401_AZURE_21_SKIN_EMULATOR_SMOKE=PASS'
cp -a "$SCRIPT/screenshots" "$ROOT/emulator-screens"
tar -C "$ROOT" -czf "$ROOT/k2401-azure-emulator-21-screens.tar.gz" emulator-screens
adb emu kill >/dev/null 2>&1 || true
kill "$EMU_PID" >/dev/null 2>&1 || true
# The existing Azure storage account remains PRIVATE; never enable public blobs.
# Container SAS is issued in the temporary GitHub OIDC job for this run only.
if [ -n "$BLOB_SAS_B64" ]; then
  PRIVATE_URL="$(printf '%s' "$BLOB_SAS_B64" | base64 -d)"
  case "$PRIVATE_URL" in
    https://tzn5androidartifacts26.blob.core.windows.net/k2401-evo-private\?*) ;;
    *) echo 'ERROR=UNEXPECTED_PRIVATE_STORAGE_URL'; exit 8;;
  esac
  BASE="$(printf '%s' "$PRIVATE_URL" | cut -d '?' -f 1)"
  QUERY="$(printf '%s' "$PRIVATE_URL" | cut -d '?' -f 2-)"
  UPLOAD_FOLDER="frozen-$(git rev-parse --short=12 HEAD)"
  for f in "$ROOT/k2401-locked-originals.tar.gz" "$ROOT/k2401-21-uhd-assets.tar.gz" \
      "$ROOT/k2401-audited-debug-not-release.apk" \
      "$REPORT/approved-originals-sha256.txt" "$REPORT/uhd-asset-sha256.txt" \
      "$REPORT/image-asset-qa.txt" "$REPORT/layout-agent.txt"; do
    name="$(basename "$f")"
    curl -fsSL --retry 3 --max-time 300 -X PUT \
      -H 'x-ms-blob-type: BlockBlob' -H 'x-ms-version: 2020-10-02' \
      -H 'Content-Type: application/octet-stream' \
      --upload-file "$f" "$BASE/$UPLOAD_FOLDER/$name?$QUERY" >/dev/null
    echo "K2401_PRIVATE_AZURE_BLOB_UPLOADED=$name"
  done
fi
echo 'K2401_AZURE_WORKSPACE_AGENTS=PASS'
