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
# Assert that settings contain actual native controls, then change the wallpaper
# preset through UI (not by changing XML behind the app's back).
adb shell input tap 45 645
adb shell uiautomator dump /sdcard/k2401-ui.xml >/dev/null
adb pull /sdcard/k2401-ui.xml "$OUT/settings-ui.xml" >/dev/null
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
xml=ET.parse(Path("projects/k2401-evo-launcher/screenshots/settings-ui.xml"))
nodes=xml.findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
for name in ("WALLPAPER","EVO Carbon","Graphite","Midnight","Alege fotografie","Setari Android","Bluetooth / Torque"):
    assert any(name in t for t in texts), f"MISSING_NATIVE_SETTING={name}"
target=next(n for n in nodes if n.attrib.get("text")=="Graphite")
points=list(map(int,re.findall(r"\d+",target.attrib["bounds"])))
x=(points[0]+points[2])//2
y=(points[1]+points[3])//2
subprocess.check_call(["adb","shell","input","tap",str(x),str(y)])
print("K2401_SETTINGS_NATIVE_CONTROLS=PASS; GRAPHITE_BUTTON_TAP=PASS")
PY
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/preferences-after-change.xml"
grep -Fq 'name="wallpaper_preset">graphite</string>' "$OUT/preferences-after-change.xml"
adb shell screencap -p /sdcard/settings-customized.png
adb pull /sdcard/settings-customized.png "$OUT/settings-customized.png" >/dev/null
echo "K2401_SETTINGS_WALLPAPER_CHANGE=PASS"
for i in $(seq 1 6); do
  adb shell input tap 45 225
  adb shell input tap 45 645
  adb shell input tap 45 120
done
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" >> "$OUT/launch.txt"
sleep 2
adb shell pidof "$APP" >/dev/null
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/preferences-after-relaunch.xml"
grep -Fq 'name="wallpaper_preset">graphite</string>' "$OUT/preferences-after-relaunch.xml"
echo "K2401_SETTINGS_PERSISTENCE_AFTER_RELAUNCH=PASS"
adb shell dumpsys meminfo "$APP" > "$OUT/memory.txt"
adb shell dumpsys gfxinfo "$APP" > "$OUT/gfxinfo.txt"
adb logcat -d > "$OUT/logcat.txt"
adb logcat -d -s AndroidRuntime:E > "$OUT/crashes.txt"
if grep -E 'Process: ro.evolauncher.k2401|ANR in ro.evolauncher.k2401' "$OUT/logcat.txt"; then
  echo "LAUNCHER_CRASH_OR_ANR_DETECTED" >&2
  exit 3
fi
echo "SIX_SCREEN_EMULATOR_SMOKE=PASS; RESOLUTION=1280x720; RESTART=PASS"
