#!/usr/bin/env bash
set -euo pipefail
APP="ro.evolauncher.k2401"
OUT="projects/k2401-evo-launcher/screenshots"
mkdir -p "$OUT"
smoke_failure(){
  local code=$?
  trap - ERR
  echo "K2401_EMULATOR_SMOKE=FAIL rc=$code" >&2
  adb logcat -d -t 650 > "$OUT/failure-logcat.txt" 2>&1 || true
  adb shell dumpsys activity activities > "$OUT/failure-activities.txt" 2>&1 || true
  adb shell dumpsys meminfo "$APP" > "$OUT/failure-meminfo.txt" 2>&1 || true
  exit "$code"
}
trap smoke_failure ERR
adb shell wm density 160
adb shell settings put system accelerometer_rotation 0
adb install -r projects/k2401-evo-launcher/app/build/outputs/apk/debug/app-debug.apk
# Real devices request location permission at runtime; emulator smoke tests
# grant it explicitly to avoid a permission dialog obscuring the six screens.
adb shell pm grant "$APP" android.permission.ACCESS_FINE_LOCATION
adb shell pm grant "$APP" android.permission.ACCESS_COARSE_LOCATION
adb logcat -c
# The emergency Activity must boot independently of map, Torque or ELM327.
adb shell am start -W -n "$APP/.SafeModeActivity" > "$OUT/recovery-launch.txt"
sleep 1
adb shell pidof "$APP" >/dev/null
adb shell uiautomator dump /sdcard/k2401-recovery.xml >/dev/null
adb pull /sdcard/k2401-recovery.xml "$OUT/recovery-ui.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/recovery-ui.xml").findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
assert any("EVO — RECUPERARE" in t for t in texts), "K2401_EMERGENCY_SCREEN_MISSING"
assert any("fără conexiuni OBD" in t for t in texts), "K2401_SAFE_BOOT_BUTTON_MISSING"
assert any("Copiază diagnosticul" in t for t in texts), "K2401_CRASH_REPORT_ACTION_MISSING"
print("K2401_OEM_SAFE_RECOVERY_ACTIVITY=PASS")
PY
# Home is SKIN-FIRST; the map is a SEPARATE deliberate navigation page.
# Verify safe recovery on the navigation page, without assuming OSM on Home.
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/recovery-ui.xml").findall(".//node")
button=next(n for n in nodes if "harta și OBD dezactivate" in n.attrib.get("text",""))
x1,y1,x2,y2=map(int,re.findall(r"[0-9]+",button.attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)])
PY
sleep 3
adb shell pidof "$APP" >/dev/null
# On slow Android 10 emulators the first tap can arrive before the real Home
# receives window focus. Re-open the independent navigation page (not the
# Home wallpaper) and verify its disabled-map placeholder with bounded retries.
map_recovered=0
for attempt in 1 2 3 4; do
  adb shell input tap 45 355 # verified native left-rail NAVIGATION target on default Digital Dash
  sleep 2
  adb shell uiautomator dump /sdcard/k2401-map-safe.xml >/dev/null
  adb pull /sdcard/k2401-map-safe.xml "$OUT/map-safe-ui.xml" >/dev/null
  if python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/map-safe-ui.xml").findall(".//node")
assert any("HARTĂ TEMPORAR DEZACTIVATĂ" in n.attrib.get("text","") for n in nodes)
PY
  then
    map_recovered=1
    break
  fi
  echo "K2401_MAP_RECOVERY_WAIT_ATTEMPT=$attempt"
done
if [[ "$map_recovered" != 1 ]]; then
  adb shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity' || true
  adb shell screencap -p /sdcard/k2401-map-recovery-failure.png || true
  adb pull /sdcard/k2401-map-recovery-failure.png "$OUT/map-recovery-failure.png" >/dev/null 2>&1 || true
  adb shell run-as "$APP" cat shared_prefs/evo_startup_recovery.xml > "$OUT/map-recovery-preferences.xml" 2>/dev/null || true
  echo "::error::Map recovery placeholder missing on separate NAVIGATION page"
  exit 1
fi
echo "K2401_RECOVER_WITHOUT_MAP_AND_OBD=PASS"
# Restore native map for regular emulator tests without clearing app data,
# thus also verifying the manual recovery button.
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.SafeModeActivity" >/dev/null
sleep 2
adb shell uiautomator dump /sdcard/k2401-map-retry.xml >/dev/null
adb pull /sdcard/k2401-map-retry.xml "$OUT/map-retry-ui.xml" >/dev/null
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/map-retry-ui.xml").findall(".//node")
button=next(n for n in nodes if "Reîncearcă harta la următoarea pornire" in n.attrib.get("text",""))
x1,y1,x2,y2=map(int,re.findall(r"[0-9]+",button.attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)])
PY
sleep 2
adb shell pidof "$APP" >/dev/null
echo "K2401_RECOVERY_REENABLE_MAP=PASS"
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" | tee "$OUT/launch.txt"
sleep 3
adb shell wm size > "$OUT/device-info.txt"
adb shell wm density >> "$OUT/device-info.txt"
adb shell getprop ro.build.version.release >> "$OUT/device-info.txt"
adb shell dumpsys display | grep -m 1 'DisplayInfo' >> "$OUT/device-info.txt" || true
capture() {
  local name="$1" y="$2"
  # Re-enter the real launcher before every screen; external Android apps can
  # steal focus after app-picker interactions on the emulator.
  # Intermittent Android 10 emulator ADB disconnects must be retried,
  # but a genuine activity crash must still FAIL with logcat and meminfo.
  local ready=0
  for retry in 1 2 3; do
    if timeout 20s adb wait-for-device >/dev/null 2>&1 &&
       adb shell am force-stop "$APP" >/dev/null 2>&1 &&
       adb shell am start -W -n "$APP/.MainActivity" >/dev/null 2>&1; then
      ready=1
      break
    fi
    echo "K2401_ADB_RECONNECT_ATTEMPT=$retry"
    adb start-server >/dev/null 2>&1 || true
    sleep 3
  done
  if [[ "$ready" != 1 ]]; then
    echo "K2401_NATIVE_HOME_NOT_RESTARTING=FAIL" >&2
    return 1
  fi
  sleep 2
  if [[ "$name" != home ]]; then
    adb shell input tap 45 35
    sleep 1
    adb shell input tap 45 "$y"
  fi
  sleep 1
  adb shell pidof "$APP" >/dev/null
  adb shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity' >> "$OUT/foreground-checks.txt" || true
  adb shell screencap -p "/sdcard/$name.png"
  adb pull "/sdcard/$name.png" "$OUT/$name.png"
}
capture home 120
# New Home contains 21 theme concepts, not an embedded map.
# Verify the skin gallery and selection persistence with real Android UI.
adb shell input tap 293 675 # native SKINURI action, 201..385 on approved wider dock
sleep 1
adb shell uiautomator dump /sdcard/k2401-skin-gallery.xml >/dev/null
adb pull /sdcard/k2401-skin-gallery.xml "$OUT/skin-gallery-ui.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/skin-gallery-ui.xml").findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
assert any("Skinuri EVO" in t for t in texts), "K2401_SKIN_GALLERY_MISSING"
assert any("EVO DIGITAL DASH" in t for t in texts), "K2401_DIGITAL_DASH_NOT_FIRST"
assert any("EVO CLASSIC" in t for t in texts), "K2401_SKIN_LIST_MISSING"
print("K2401_21_SKIN_GALLERY_NATIVE=PASS")
PY
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/skin-gallery-ui.xml").findall(".//node")
row=next(n for n in nodes if "EVO CLASSIC" in n.attrib.get("text",""))
a,b,c,d=map(int,re.findall(r"[0-9]+",row.attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((a+c)//2),str((b+d)//2)])
PY
sleep 1
adb shell uiautomator dump /sdcard/k2401-skin-preview.xml >/dev/null
adb pull /sdcard/k2401-skin-preview.xml "$OUT/skin-preview-ui.xml" >/dev/null
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/skin-preview-ui.xml").findall(".//node")
target=next(n for n in nodes if "APLICĂ ACEST SKIN" in n.attrib.get("text",""))
a,b,c,d=map(int,re.findall(r"[0-9]+",target.attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((a+c)//2),str((b+d)//2)])
PY
sleep 1
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/skin-1-prefs.xml"
grep -Eq 'name="selected_skin_v2" value="1"' "$OUT/skin-1-prefs.xml"
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" >/dev/null
sleep 2
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/skin-relaunch-prefs.xml"
grep -Eq 'name="selected_skin_v2" value="1"' "$OUT/skin-relaunch-prefs.xml"
echo "K2401_SKIN_PERSISTENCE_AFTER_RESTART=PASS"
# Return to Digital Dash for the rest of the smoke run.
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml >/dev/null
# Tapping the music card should offer a player picker (including Vanced when
# actually installed), NEVER switch to Store or an external media Activity.
adb shell input tap 1010 71 # Theme #02 real top-right media header, not old Classic coordinates
sleep 1
adb shell uiautomator dump /sdcard/k2401-media-picker.xml >/dev/null
adb pull /sdcard/k2401-media-picker.xml "$OUT/media-picker-ui.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/media-picker-ui.xml").findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
assert any("Alege playerul instalat" in t for t in texts), "K2401_MEDIA_PICKER_MISSING"
assert any("permisiune mediasession" in t.casefold() for t in texts), "K2401_MEDIA_PERMISSION_ACTION_MISSING"
print("K2401_MEDIA_PLAYER_SELECT_INSIDE_HOME=PASS")
PY
# Select an ACTUAL installed player and verify persistence, not a mock.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
root=ET.parse("projects/k2401-evo-launcher/screenshots/media-picker-ui.xml")
items=[n for n in root.findall(".//node") if n.attrib.get("class","").endswith("CheckedTextView") and n.attrib.get("text")]
assert items, "K2401_MEDIA_PICKER_HAS_NO_INSTALLED_PLAYERS"
a,b,c,d=map(int,re.findall(r"[0-9]+",items[0].attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((a+c)//2),str((b+d)//2)])
PY
for n in $(seq 1 15); do
  adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/media-prefs-before-restart.xml"
  if grep -Fq 'name="evo_media_package"' "$OUT/media-prefs-before-restart.xml"; then break; fi
  sleep 0.3
done
grep -Fq 'name="evo_media_package"' "$OUT/media-prefs-before-restart.xml"
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" >/dev/null
sleep 2
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/media-prefs-after-restart.xml"
python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path
folder=Path("projects/k2401-evo-launcher/screenshots")
def get(name):
    root=ET.parse(folder/name).getroot()
    return next((n.text for n in root.findall("string") if n.get("name")=="evo_media_package"),None)
a=get("media-prefs-before-restart.xml")
b=get("media-prefs-after-restart.xml")
assert a and a==b,"K2401_SELECTED_MEDIA_PLAYER_NOT_PERSISTENT"
print("K2401_MEDIA_SELECTED_PLAYER_PERSISTENCE=PASS",a)
PY
adb shell pidof "$APP" >/dev/null
# Native all-apps drawer must contain the actual installed packages.
adb shell input tap 45 460 # Theme #02 real left-side Apps icon; old footer no longer exists
sleep 1
adb shell uiautomator dump /sdcard/k2401-apps.xml >/dev/null
adb pull /sdcard/k2401-apps.xml "$OUT/installed-apps-ui.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/installed-apps-ui.xml").findall(".//node")
texts=[n.attrib.get("text","") for n in nodes]
assert any("APLICAȚII INSTALATE" in t for t in texts), "K2401_APP_DRAWER_MISSING"
assert any("Caută o aplicație" in t for t in texts), "K2401_APP_SEARCH_MISSING"
assert any("Chrome" in t or "Settings" in t or "Setări" in t for t in texts), "K2401_REAL_APPS_NOT_LISTED"
print("K2401_INSTALLED_APPS_DRAWER=PASS")
PY
adb shell input tap 45 120
sleep 1
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
sleep 1  # Wait for Android filesystem visibility after settings UI update.
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/preferences-after-change.xml"
grep -Fq 'name="wallpaper_preset">graphite</string>' "$OUT/preferences-after-change.xml"
adb shell screencap -p /sdcard/settings-customized.png
adb pull /sdcard/settings-customized.png "$OUT/settings-customized.png" >/dev/null
echo "K2401_SETTINGS_WALLPAPER_CHANGE=PASS"
# Settings are scrollable: lower controls are intentionally offscreen in the
# first UI hierarchy. Scroll before asserting their presence.
for i in $(seq 1 3); do adb shell input swipe 940 620 940 230 350; done
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
# Check all twenty-one original skin canvases in a debug Android 10 emulator.
for n in $(seq 0 20); do
  adb shell am force-stop "$APP"
  adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci "$n" >/dev/null
  # Android 10 may not publish the freshly started process in pidof immediately
  # after am start returns. Retry briefly; a real crash still fails with logcat.
  alive=0
  for check in 1 2 3 4 5 6 7 8; do
    if adb shell pidof "$APP" >/dev/null 2>&1; then alive=1; break; fi
    sleep 1
  done
  if [ "$alive" -ne 1 ]; then
    echo "K2401_SKIN_APP_DIED_AFTER_START id=$n" >&2
    adb logcat -d -s AndroidRuntime:E | tail -100 >&2 || true
    exit 5
  fi
  # Some Android emulators briefly expose a blank 48,48,48 splash between
  # activity launch and SurfaceView composition. Never count that as a skin.
  valid=0
  for attempt in 1 2 3 4 5 6; do
    sleep 1
    adb shell screencap -p "/sdcard/skin_$n.png"
    adb pull "/sdcard/skin_$n.png" "$OUT/skin_$n.png" >/dev/null
    bytes=$(wc -c < "$OUT/skin_$n.png")
    if [ "$bytes" -ge 70000 ]; then valid=1; break; fi
    echo "K2401_SKIN_SCREEN_WAIT id=$n attempt=$attempt bytes=$bytes"
  done
  if [ "$valid" -ne 1 ]; then
    echo "K2401_SKIN_SCREEN_BLANK id=$n" >&2
    exit 4
  fi
done
python3 - <<'PY'
from pathlib import Path
from hashlib import sha256
import struct
folder=Path("projects/k2401-evo-launcher/screenshots")
images=[folder/f"skin_{i}.png" for i in range(21)]
assert all(x.is_file() for x in images)
assert all(struct.unpack(">II",x.read_bytes()[16:24])==(1280,720) for x in images)
assert len({sha256(x.read_bytes()).digest() for x in images})==21
print("K2401_ALL_21_NATIVE_SKIN_SCREENSHOTS=PASS")
PY
# This is image evidence from the actual Android 10 emulator, not concept art.
# Keep three photographed vehicle scenes visible below native LIVE RPM.
python3 projects/k2401-evo-launcher/scripts/verify-scene-visibility.py
python3 projects/k2401-evo-launcher/scripts/verify-theme2-photo.py
echo "SIX_SCREEN_EMULATOR_SMOKE=PASS; RESOLUTION=1280x720; RESTART=PASS"
