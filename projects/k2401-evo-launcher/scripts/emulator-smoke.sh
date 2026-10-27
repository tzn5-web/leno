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
  # Home does not display the side navigation bar.
  if [[ "$name" != home ]]; then
    adb shell input tap 45 35  # Home header opens app menu; on other pages no-op
    adb shell input tap 45 "$y"
  fi
  sleep 1
  adb shell pidof "$APP" >/dev/null
  adb shell screencap -p "/sdcard/$name.png"
  adb pull "/sdcard/$name.png" "$OUT/$name.png"
}
capture home 120
# Native dock is inspectable by Android accessibility, unlike decorative canvas.
adb shell uiautomator dump /sdcard/k2401-dock.xml >/dev/null
adb pull /sdcard/k2401-dock.xml "$OUT/dock-ui.xml" >/dev/null
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
nodes=ET.parse(Path("projects/k2401-evo-launcher/screenshots/dock-ui.xml")).findall(".//node")
assert any(n.attrib.get("text")=="Adaugă" for n in nodes), "K2401_DOCK_ADD_MISSING"
assert any(n.attrib.get("content-desc","").startswith("Adaugă aplicație") for n in nodes), "K2401_DOCK_ACCESSIBILITY_MISSING"
print("K2401_REAL_ICON_DOCK_NATIVE=PASS")
PY
# Exercise the real app picker and persistence. The emulator's launcher-app
# inventory varies; select the first actual Android launcher entry.
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/dock-ui.xml").findall(".//node")
target=next(n for n in nodes if n.attrib.get("content-desc")=="Adaugă aplicație")
x1,y1,x2,y2=map(int,re.findall(r"[0-9]+",target.attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)])
PY
sleep 1
adb shell uiautomator dump /sdcard/k2401-picker.xml >/dev/null
adb pull /sdcard/k2401-picker.xml "$OUT/dock-picker.xml" >/dev/null
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/dock-picker.xml").findall(".//node")
assert any(n.attrib.get("text")=="Alege aplicația" for n in nodes), "K2401_DOCK_PICKER_MISSING"
items=[n for n in nodes if n.attrib.get("class","").endswith(("CheckedTextView","TextView")) and n.attrib.get("text") and n.attrib.get("text") not in ("Alege aplicația","ANULEAZĂ","Anulează","CANCEL")]
assert items, "K2401_DOCK_PICKER_EMPTY"
x1,y1,x2,y2=map(int,re.findall(r"[0-9]+",items[0].attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)])
print("K2401_DOCK_PICKER_SELECT=PASS")
PY
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/dock-prefs-before-restart.xml"
grep -Fq 'name="dock_pins_v1"' "$OUT/dock-prefs-before-restart.xml"
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" >/dev/null
sleep 2
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/dock-prefs-after-restart.xml"
python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path
folder=Path("projects/k2401-evo-launcher/screenshots")
def get(filename):
    root=ET.parse(folder/filename).getroot()
    return next(n.text or "" for n in root.findall("string") if n.attrib.get("name")=="dock_pins_v1")
a,b=get("dock-prefs-before-restart.xml"),get("dock-prefs-after-restart.xml")
assert a and a==b, "K2401_DOCK_PINS_NOT_PERSISTENT"
print("K2401_DOCK_PERSISTENCE_AFTER_RESTART=PASS")
PY
adb shell input tap 45 35  # Home -> app menu with side navigation
sleep 1
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
for name in ("WALLPAPER","EVO Carbon","Graphite","Midnight","Alege fotografie"):
    assert any(name in t for t in texts), f"MISSING_NATIVE_SETTING={name}"
target=next(n for n in nodes if n.attrib.get("text")=="Graphite")
points=list(map(int,re.findall(r"[0-9]+",target.attrib["bounds"])))
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
# Settings are scrollable: lower controls are intentionally offscreen in the
# first UI hierarchy. Scroll before asserting their presence.
adb shell input swipe 940 620 940 240 550
sleep 1
adb shell uiautomator dump /sdcard/k2401-ui-scrolled.xml >/dev/null
adb pull /sdcard/k2401-ui-scrolled.xml "$OUT/settings-ui-scrolled.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/settings-ui-scrolled.xml").findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
for name in ("Setari Android","Bluetooth / Torque","GPS / Locatie"):
    assert any(name in t for t in texts), f"MISSING_SCROLLABLE_SETTING={name}"
print("K2401_SCROLLABLE_SETTINGS=PASS")
PY
for i in $(seq 1 6); do
  adb shell input tap 45 35  # Home -> app menu with side navigation
  adb shell input tap 45 225 # Music
  adb shell input tap 45 645 # Settings
  adb shell input tap 45 120 # Home
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
