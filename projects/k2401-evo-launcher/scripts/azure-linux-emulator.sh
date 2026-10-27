#!/usr/bin/env bash
# K2401 Android 10 emulator on a real Azure Ubuntu Dsv3 VM with /dev/kvm.
# Launched by GitHub Actions from the main branch's existing Azure OIDC identity.
# No simulated ECU readings or fabricated GPS/media results.
set -Eeuo pipefail
umask 077
SAS_B64="${1:?SAS URL base64 required}"
EXPECTED_SHA="${2:?APK sha256 required}"
ROOT=/opt/k2401-android10
RESULTS="$ROOT/results"
mkdir -p "$RESULTS"
STATUS=FAIL
DETAIL=NOT_STARTED
BASE=""
QUERY=""
if [[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{64}$ ]]; then
  SAS_URL="$(printf %s "$SAS_B64" | base64 -d)"
  BASE="${SAS_URL%%\?*}"
  QUERY="${SAS_URL#*\?}"
fi
upload_results() {
  local rc=$?
  trap - EXIT
  set +e
  if [[ "$rc" -eq 0 ]]; then STATUS=PASS; DETAIL=ANDROID10_KVM_SIX_SCREENS_WALLPAPER_PERSISTENCE; fi
  printf 'STATUS=%s\nDETAIL=%s\nAZURE_VM=LINUX_KVM\nANDROID=10_API29\nTORQUE_REAL_ECU=NOT_TESTED\nYOUTUBE_MUSIC_REAL_SESSION=NOT_TESTED\nGPS_PHYSICAL=NOT_TESTED\n' "$STATUS" "$DETAIL" > "$RESULTS/report.txt"
  if [[ -n "$BASE" && -n "$QUERY" ]]; then
    for f in "$RESULTS"/*; do
      [[ -f "$f" ]] || continue
      name="$(basename "$f")"
      mime=text/plain
      [[ "$name" == *.png ]] && mime=image/png
      curl --silent --show-error --fail --retry 2 --max-time 75 -X PUT \
        -H 'x-ms-blob-type: BlockBlob' -H "Content-Type: $mime" \
        --data-binary "@$f" "$BASE/results/$name?$QUERY" >/dev/null || true
    done
  fi
  [[ -n "${EMU_PID:-}" ]] && kill "$EMU_PID" 2>/dev/null || true
  echo "K2401_AZURE_TEST_STATUS=$STATUS"
  echo "DETAIL=$DETAIL"
  exit "$rc"
}
trap upload_results EXIT
[[ "$BASE" =~ ^https://[a-z0-9]+\.blob\.core\.windows\.net/[a-z0-9-]+$ ]] || { DETAIL=INVALID_TRANSFER_ENDPOINT; exit 2; }
[[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{64}$ ]] || { DETAIL=INVALID_SHA; exit 2; }
DETAIL=KVM_HARDWARE_PREFLIGHT
grep -Eq '(vmx|svm)' /proc/cpuinfo || { DETAIL=AZURE_NESTED_VIRTUALIZATION_CPU_FLAG_ABSENT; exit 3; }
test -c /dev/kvm || { DETAIL=AZURE_KVM_DEVICE_MISSING; exit 3; }
test -r /dev/kvm && test -w /dev/kvm || { DETAIL=AZURE_KVM_PERMISSION_DENIED; exit 3; }
echo 'AZURE_NESTED_KVM_PREFLIGHT=PASS' > "$RESULTS/acceleration.txt"
DETAIL=APK_TRANSFER
curl -fsSL --retry 3 --max-time 120 "$BASE/launcher.apk?$QUERY" -o "$ROOT/launcher.apk"
echo "$EXPECTED_SHA  $ROOT/launcher.apk" | sha256sum -c - > "$RESULTS/apk-hash.txt"
DETAIL=ANDROID_SDK_SETUP
export DEBIAN_FRONTEND=noninteractive
timeout 15m apt-get update -qq > "$RESULTS/apt.log" 2>&1
timeout 15m apt-get install -y -qq curl unzip ca-certificates python3 openjdk-17-jre-headless \
  libpulse0 libnss3 libx11-6 libxcomposite1 libxcursor1 libxi6 libxrandr2 \
  libxrender1 libxtst6 libasound2 libglib2.0-0 libdbus-1-3 libfontconfig1 \
  libfreetype6 libstdc++6 >> "$RESULTS/apt.log" 2>&1
export ANDROID_HOME="$ROOT/android-sdk" ANDROID_SDK_ROOT="$ROOT/android-sdk"
export ANDROID_AVD_HOME="$ROOT/avd" JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
mkdir -p "$ANDROID_HOME/cmdline-tools/latest" "$ANDROID_AVD_HOME"
curl -fsSL --retry 3 --max-time 240 \
  https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip -o "$ROOT/commandline-tools.zip"
mkdir -p "$ROOT/sdk-unpacked"
unzip -q "$ROOT/commandline-tools.zip" -d "$ROOT/sdk-unpacked"
mv "$ROOT/sdk-unpacked/cmdline-tools/"* "$ANDROID_HOME/cmdline-tools/latest/"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
(yes | sdkmanager --sdk_root="$ANDROID_HOME" --licenses > "$RESULTS/licenses.log" 2>&1) || true
timeout 20m sdkmanager --sdk_root="$ANDROID_HOME" \
  'platform-tools' 'emulator' 'system-images;android-29;google_apis;x86_64' > "$RESULTS/sdk.log" 2>&1
printf 'no\n' | avdmanager create avd --force -n k2401azure \
  -k 'system-images;android-29;google_apis;x86_64' > "$RESULTS/avd.log" 2>&1
emulator -accel-check >> "$RESULTS/acceleration.txt" 2>&1
DETAIL=ANDROID_EMULATOR_BOOT
adb start-server > "$RESULTS/adb-start.txt" 2>&1
emulator -avd k2401azure -no-window -no-audio -no-boot-anim -no-snapshot \
  -gpu swiftshader_indirect -memory 2048 -partition-size 2048 -accel on \
  -skin 1280x720 > "$RESULTS/emulator.log" 2>&1 &
EMU_PID=$!
booted=false
for i in $(seq 1 100); do
  if [[ "$(adb -e shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; then booted=true; break; fi
  kill -0 "$EMU_PID" 2>/dev/null || { DETAIL=EMULATOR_EXITED_EARLY; exit 4; }
  sleep 5
done
[[ "$booted" == true ]] || { DETAIL=EMULATOR_BOOT_TIMEOUT; exit 4; }
ANDROID="$(adb -e shell getprop ro.build.version.release | tr -d '\r')"
[[ "$ANDROID" == 10 ]] || { DETAIL=NOT_ANDROID_10; exit 5; }
adb -e shell wm size 1280x720
adb -e shell wm density 160
DETAIL=APK_INSTALL_AND_SIX_SCREENS
adb -e install -r "$ROOT/launcher.apk" > "$RESULTS/install.txt"
adb -e shell am start -W -n ro.evolauncher.k2401/.MainActivity > "$RESULTS/launch.txt"
sleep 4
for item in home:120 music:225 navigation:332 car:435 apps:545 settings:645; do
  page="${item%%:*}"; y="${item#*:}"
  adb -e shell input tap 45 "$y"
  sleep 2
  adb -e shell pidof ro.evolauncher.k2401 >/dev/null
  adb -e shell screencap -p "/sdcard/$page.png"
  adb -e pull "/sdcard/$page.png" "$RESULTS/$page.png" >/dev/null
done
python3 - "$RESULTS" <<'PY'
from pathlib import Path
from struct import unpack
import sys
folder=Path(sys.argv[1])
for name in ("home","music","navigation","car","apps","settings"):
    data=(folder/(name+".png")).read_bytes()
    assert data[:8]==bytes.fromhex("89504e470d0a1a0a"),name
    w,h=unpack(">II",data[16:24])
    assert (w,h)==(1280,720),(name,w,h)
print("AZURE_SIX_SCREEN_1280x720=PASS")
PY
DETAIL=WALLPAPER_UI_AND_PERSISTENCE
adb -e shell uiautomator dump /sdcard/settings-ui.xml >/dev/null
adb -e pull /sdcard/settings-ui.xml "$RESULTS/settings-ui.xml" >/dev/null
python3 - "$RESULTS/settings-ui.xml" <<'PY'
import re,subprocess,sys,xml.etree.ElementTree as ET
nodes=ET.parse(sys.argv[1]).findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
for name in ("WALLPAPER","EVO Carbon","Graphite","Midnight","Alege fotografie"):
    assert any(name in t for t in texts),f"MISSING_SETTING={name}"
n=next(n for n in nodes if n.attrib.get("text")=="Graphite")
x1,y1,x2,y2=map(int,re.findall(r"\d+",n.attrib["bounds"]))
subprocess.check_call(["adb","-e","shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)])
print("AZURE_WALLPAPER_BUTTON=PASS")
PY
sleep 1
adb -e shell uiautomator dump /sdcard/changed.xml >/dev/null
adb -e pull /sdcard/changed.xml "$RESULTS/changed.xml" >/dev/null
grep -q 'Fundal activ: GRAPHITE' "$RESULTS/changed.xml" || { DETAIL=WALLPAPER_CHANGE_NOT_REFLECTED; exit 6; }
adb -e shell am force-stop ro.evolauncher.k2401
adb -e shell am start -W -n ro.evolauncher.k2401/.MainActivity >> "$RESULTS/launch.txt"
adb -e shell input tap 45 645
sleep 2
adb -e shell uiautomator dump /sdcard/relaunch.xml >/dev/null
adb -e pull /sdcard/relaunch.xml "$RESULTS/relaunch.xml" >/dev/null
grep -q 'Fundal activ: GRAPHITE' "$RESULTS/relaunch.xml" || { DETAIL=WALLPAPER_NOT_PERSISTED; exit 6; }
adb -e shell screencap -p /sdcard/wallpaper-persisted.png
adb -e pull /sdcard/wallpaper-persisted.png "$RESULTS/wallpaper-persisted.png" >/dev/null
adb -e logcat -d -s AndroidRuntime:E > "$RESULTS/crashes.txt"
if grep -E 'Process: ro.evolauncher.k2401|ANR in ro.evolauncher.k2401' "$RESULTS/crashes.txt"; then
  DETAIL=APP_CRASH_OR_ANR
  exit 7
fi
echo 'AZURE_ANDROID10_WALLPAPER_PERSISTENCE=PASS' > "$RESULTS/verification.txt"
DETAIL=ANDROID10_KVM_SIX_SCREENS_WALLPAPER_PERSISTENCE
