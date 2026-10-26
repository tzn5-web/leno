#!/usr/bin/env bash
set -euo pipefail
APP="ro.evolauncher.k2401"
OUT="projects/k2401-evo-launcher/screenshots"
mkdir -p "$OUT"
adb shell wm density 160
adb shell settings put system accelerometer_rotation 0
adb install -r projects/k2401-evo-launcher/app/build/outputs/apk/debug/app-debug.apk
adb logcat -c
adb shell am start -W -n "$APP/.MainActivity" | tee "$OUT/launch.txt"
sleep 3
adb shell wm size > "$OUT/device-info.txt"
adb shell wm density >> "$OUT/device-info.txt"
adb shell getprop ro.build.version.release >> "$OUT/device-info.txt"
adb shell dumpsys display | grep -m 1 'DisplayInfo' >> "$OUT/device-info.txt" || true
capture() {
  local name="$1" y="$2"
  adb shell input tap 45 "$y"
  sleep 1
  adb shell pidof "$APP" >/dev/null
  adb shell screencap -p "/sdcard/$name.png"
  adb pull "/sdcard/$name.png" "$OUT/$name.png"
}
capture home 120
capture music 225
capture navigation 332
capture car 435
capture apps 545
capture settings 645
python3 - <<'PY'
from pathlib import Path
from struct import unpack
folder = Path("projects/k2401-evo-launcher/screenshots")
for name in ("home","music","navigation","car","apps","settings"):
    data = (folder / (name + ".png")).read_bytes()
    assert data[:8] == bytes.fromhex("89504e470d0a1a0a"), name + ": invalid screenshot"
    w,h = unpack(">II",data[16:24])
    print(f"SCREEN {name}: {w}x{h}")
    assert (w,h) == (1280,720), f"{name}: incorrect landscape resolution {w}x{h}"
PY
for i in $(seq 1 6); do
  adb shell input tap 45 225
  adb shell input tap 45 645
  adb shell input tap 45 120
done
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" >> "$OUT/launch.txt"
sleep 2
adb shell pidof "$APP" >/dev/null
adb shell dumpsys meminfo "$APP" > "$OUT/memory.txt"
adb shell dumpsys gfxinfo "$APP" > "$OUT/gfxinfo.txt"
adb logcat -d > "$OUT/logcat.txt"
adb logcat -d -s AndroidRuntime:E > "$OUT/crashes.txt"
if grep -E 'Process: ro.evolauncher.k2401|ANR in ro.evolauncher.k2401' "$OUT/logcat.txt"; then
  echo "LAUNCHER_CRASH_OR_ANR_DETECTED" >&2
  exit 3
fi
echo "SIX_SCREEN_EMULATOR_SMOKE=PASS; RESOLUTION=1280x720; RESTART=PASS"
