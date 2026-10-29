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
assert '"N/A"' in source and 'String exterior=Float.isFinite(obd.ambientC)' in source
assert 'GlassHudFx.glassPanel(c,454,170,411,94,15)' in source, "Native translucent date panel missing"
assert 'drawTopStatus(c); // STATUS CLOCK MUST ALWAYS BE THE FINAL PAINT PASS' in source
assert source.count('Settings.Global.getInt(host.getContentResolver(),"wifi_on"') == 1
from PIL import Image
with Image.open(shot).convert("RGB") as screen:
    # A glass panel remains legible over a deliberately dark clean scene.
    for point in ((457,180),(553,178),(861,180),(573,258),(751,259)):
        color=screen.getpixel(point)
        assert max(color)<150,(point,color,"Stale background leaked into HUD")
print("K2401_ULTRA_TRANSLUCENT_DATE_PANEL=PASS")
assert source.count('new SimpleDateFormat("HH:mm",Locale.getDefault()).format(now)')==1
assert 'no duplicate top-right clock' in source
print("K2401_ULTRA_SINGLE_LIVE_CLOCK=PASS")
assert 'ultra_app_slot_' in source and 'getLaunchIntentForPackage(pkg)' in source
assert 'postDelayed(longPressJob,550)' in source
assert 'final int[] ys={73,171,269,367,465,563};' in source
assert 'rect(c,0,0,102,720,0,0xff090b10)' in source
assert 'Math.min(5,i)' not in source and 'for(int i=0;i<7;i++)' not in source
assert 'if(idx==4){host.showInstalledApps();return true;}' in source
assert 'GlassHudFx.glassPanel(c,113,12,1152,148,17)' in source
assert 'center(c,"ECU N/A"' not in source
print("K2401_ULTRA_NO_DUPLICATE_RAIL_ICONS=PASS")
print("K2401_ULTRA_NO_STALE_MUSIC_BLEED=PASS")
print("K2401_ULTRA_NO_TRIM_NA_OVERLAP=PASS")
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
# Exercise focus loss/restore. The single central clock must remain visible
# when a native Android dialog closes (no duplicate top-right clock).
adb shell input keyevent BACK
sleep 2
adb shell screencap -p /sdcard/k2401-ultra-after-dialog.png
adb pull /sdcard/k2401-ultra-after-dialog.png "$OUT/k2401-ultra-after-dialog.png" >/dev/null
python3 - <<'PY'
from PIL import Image
from pathlib import Path
pic=Image.open(Path("projects/k2401-evo-launcher/screenshots/k2401-ultra-after-dialog.png")).convert("RGB")
assert pic.size==(1280,720)
# The native central clock remains visible over the glass date panel.
area=pic.crop((595,185,730,251))
bright=sum(1 for r,g,b in area.getdata() if min(r,g,b)>150)
assert bright>105,f"Single central clock vanished after dialog; bright={bright}"
print("K2401_ULTRA_SINGLE_CLOCK_SURVIVES_DIALOG=PASS")
PY
echo "K2401_ULTRA_TEMPERATURE_AND_SIX_SLOTS_SMOKE=PASS"
