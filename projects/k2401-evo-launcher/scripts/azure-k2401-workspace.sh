#!/usr/bin/env bash
# K2401 existing Azure Linux VM: frozen sources, no invented UI or vehicle images.
set -Eeuo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
ROOT=/opt/k2401-evo-workspace
REPORT="$ROOT/reports"
mkdir -p "$REPORT" "$ROOT/original-immutable" "$ROOT/generated" "$ROOT/tools"
exec > >(tee -a "$REPORT/azure-setup.log") 2>&1
trap 'echo "K2401_VM_RUN_EXIT=$?"' EXIT
EXPECTED_SHA=''
for arg in "$@"; do
  case "$arg" in ExpectedSha=*) EXPECTED_SHA="$(printf '%s' "$arg" | cut -d = -f 2)";; esac
done
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR=INVALID_EXPECTED_SHA'; exit 2; }
date -u --iso-8601=seconds > "$REPORT/started-utc.txt"
echo "K2401_FROZEN_SHA=$EXPECTED_SHA"
apt-get update -qq
apt-get install -y -qq git ca-certificates curl unzip zip jq openjdk-17-jdk-headless python3 python3-pip python3-venv python3-dev build-essential libgl1 >/dev/null
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
( cd "$ROOT/generated" && sha256sum clean/skin_??.webp uhd/skin_??.webp | sort ) > "$REPORT/uhd-asset-sha256.txt"
tar -C "$ROOT" -czf "$ROOT/k2401-locked-originals.tar.gz" original-immutable reports/approved-originals-sha256.txt
tar -C "$ROOT" -czf "$ROOT/k2401-21-uhd-assets.tar.gz" generated reports/uhd-asset-sha256.txt
du -h "$ROOT"/*.tar.gz | tee "$REPORT/archive-sizes.txt"
echo 'K2401_AZURE_WORKSPACE_AGENTS=PASS'
