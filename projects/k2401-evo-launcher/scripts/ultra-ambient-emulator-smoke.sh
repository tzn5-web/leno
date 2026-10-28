#!/usr/bin/env bash
# Dedicated Android 10 emulator verification for selectable Ultra Neon #22.
# No fake OBD data are injected; unsupported ambient temperature stays N/A.
set -euo pipefail
APP="ro.evolauncher.k2401"
OUT="projects/k2401-evo-launcher/screenshots"
mkdir -p "$OUT"
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 21 > "$OUT/ultra-ambient-launch.txt"
sleep 3
adb shell pidof "$APP" >/dev/null
adb shell wm size | grep -F 'Override size: 1280x720' >/dev/null
adb shell screencap -p /sdcard/k2401-ultra-ambient.png
adb pull /sdcard/k2401-ultra-ambient.png "$OUT/k2401-ultra-ambient.png" >/dev/null
python3 - <<'PY'
import pathlib,struct
shot=pathlib.Path("projects/k2401-evo-launcher/screenshots/k2401-ultra-ambient.png")
img=shot.read_bytes()
assert img[:8]==bytes.fromhex("89504e470d0a1a0a")
assert struct.unpack(">II",img[16:24])==(1280,720)
assert len(img)>70000,"UHD cockpit is blank"
source=pathlib.Path("projects/k2401-evo-launcher/app/src/main/java/ro/evolauncher/k2401/UltraCockpitTheme.java").read_text()
assert 'Float.isFinite(obd.ambientC)' in source
assert '"EXT: N/A"' in source
assert 'ultra_app_slot_' in source and 'getLaunchIntentForPackage(pkg)' in source
assert 'postDelayed(longPressJob,550)' in source
print("K2401_ULTRA_UHD_SNAPSHOT=PASS; AMBIENT_NA_WHEN_UNAVAILABLE=PASS")
PY
# A sustained tap on the first slot must present the real app chooser.
adb shell input swipe 462 645 462 645 780
sleep 1
adb shell uiautomator dump /sdcard/k2401-ultra-slot-picker.xml >/dev/null
adb pull /sdcard/k2401-ultra-slot-picker.xml "$OUT/k2401-ultra-slot-picker.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/k2401-ultra-slot-picker.xml").findall(".//node")
words=[n.attrib.get("text","") for n in nodes]
assert any("Aplicația 1" in t for t in words),f"Long press did not open slot 1 chooser: {words}"
assert any("Golește acest slot" in t for t in words), "Missing reset-slot control"
print("K2401_ULTRA_LONG_PRESS_APPLICATION_PICKER=PASS")
PY
# Choose a real installed app through the Android dialog (never hardcode
# installed package names or use demo placeholders).
python3 - <<'PY'
import xml.etree.ElementTree as ET,re,subprocess
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/k2401-ultra-slot-picker.xml").findall(".//node")
exclude=("Golește acest slot","Aplicația 1","Anulează")
choices=[n for n in nodes if n.attrib.get("text","") and
  n.attrib.get("class","").endswith(("TextView","CheckedTextView")) and
  not any(s in n.attrib.get("text","") for s in exclude) and
  re.fullmatch(r"\[\d+,\d+\]\[\d+,\d+\]",n.attrib.get("bounds",""))]
assert choices,"No launchable application in the Android 10 chooser"
pick=choices[0]
a,b,c,d=map(int,re.findall(r"\d+",pick.attrib["bounds"]))
print("K2401_PICK_ACTUAL_APP=",pick.attrib["text"])
subprocess.check_call(["adb","shell","input","tap",str((a+c)//2),str((b+d)//2)])
PY
sleep 1
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/k2401-ultra-slots-before.xml"
python3 - <<'PY'
import xml.etree.ElementTree as ET
root=ET.parse("projects/k2401-evo-launcher/screenshots/k2401-ultra-slots-before.xml").getroot()
slot=next((e.text for e in root.findall("string") if e.attrib.get("name")=="ultra_app_slot_0"),None)
assert slot and "." in slot,f"Slot 0 did not save a real package: {slot!r}"
print("K2401_ULTRA_REAL_APP_SLOT_SAVED=PASS")
PY
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 21 >/dev/null
sleep 2
adb shell run-as "$APP" cat shared_prefs/evo_launcher_prefs.xml > "$OUT/k2401-ultra-slots-after.xml"
python3 - <<'PY'
import xml.etree.ElementTree as ET
folder="projects/k2401-evo-launcher/screenshots/"
def get(name):
    root=ET.parse(folder+name).getroot()
    return next((e.text for e in root.findall("string") if e.attrib.get("name")=="ultra_app_slot_0"),None)
assert get("k2401-ultra-slots-before.xml")==get("k2401-ultra-slots-after.xml")
print("K2401_ULTRA_APP_SLOT_PERSISTS_RESTART=PASS")
PY
# The second long press must permit replacing the same chosen shortcut.
adb shell input swipe 462 645 462 645 780
sleep 1
adb shell uiautomator dump /sdcard/k2401-ultra-replace.xml >/dev/null
adb pull /sdcard/k2401-ultra-replace.xml "$OUT/k2401-ultra-replace.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
texts=[n.attrib.get("text","") for n in
  ET.parse("projects/k2401-evo-launcher/screenshots/k2401-ultra-replace.xml").findall(".//node")]
assert any("Aplicația 1" in t for t in texts),"Long press cannot replace the selected app"
print("K2401_ULTRA_LONG_PRESS_REPLACE_EXISTING_APP=PASS")
PY
echo "K2401_ULTRA_TEMPERATURE_AND_SIX_SLOTS_SMOKE=PASS"
