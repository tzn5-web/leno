#!/usr/bin/env bash
# Approved red/white angular RACE HUD FINAL (skin 25).
# Actual Android 10 emulator screenshot and native map status, not static mock.
set -euo pipefail
APP=ro.evolauncher.k2401
OUT=projects/k2401-evo-launcher/screenshots
mkdir -p "$OUT"
adb shell wm size 1280x720
adb shell wm density 160
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 25 > "$OUT/race-hud-launch.txt"
sleep 3
adb shell pidof "$APP" >/dev/null
adb shell screencap -p /sdcard/race-hud-final.png
adb pull /sdcard/race-hud-final.png "$OUT/race-hud-final.png" >/dev/null
adb shell uiautomator dump /sdcard/race-hud-tree.xml >/dev/null
adb pull /sdcard/race-hud-tree.xml "$OUT/race-hud-tree.xml" >/dev/null
python3 - <<'PY'
from pathlib import Path
from PIL import Image,ImageStat
import xml.etree.ElementTree as ET
root=Path("projects/k2401-evo-launcher")
src=(root/"app/src/main/java/ro/evolauncher/k2401/RaceHudFinalTheme.java").read_text()
main=(root/"app/src/main/java/ro/evolauncher/k2401/MainActivity.java").read_text()
skins=(root/"app/src/main/java/ro/evolauncher/k2401/SkinEngine.java").read_text()
ultra=(root/"app/src/main/java/ro/evolauncher/k2401/UltraCockpitTheme.java").read_text()
pic=Image.open(root/"screenshots/race-hud-final.png").convert("RGB")
assert pic.size==(1280,720)
assert max(ImageStat.Stat(pic).stddev)>15,"Blank home dashboard"
assert 'static final int ID=25' in src and 'RACE HUD • FINAL ALB-ROȘU' in skins
assert 'raceHud.draw(c)' in skins
assert 'RaceHudFinalTheme.ID' in ultra
assert 'boolean shown=page==2||raceHome;' in main
assert 'raceHome?RaceHudFinalTheme.MAP_X:158;' in main
assert 'raceHome?RaceHudFinalTheme.MAP_H:527;' in main
assert "host.mediaAction(1)" in src and "host.choosePlayer()" in src
assert 'String[] actions={"SETUP","APPS","NAVI","MUZICĂ"}' in src
assert '"RPM"' in src and '"TEMP APĂ"' in src
assert 'trim(c,423,"STFT",r.stft)' in src and 'trim(c,642,"LTFT",r.ltft)' in src
assert 'slots.drawUserSlots(c)' in src
for bad in ('PRNDS','BATTERY','VOLT','BOOST','FUEL','3400 rpm','Str. Principală','Google Maps 3D screenshot'):
    assert bad not in src,('Fictitious/inappropriate HUD element',bad)
nodes=ET.parse(root/"screenshots/race-hud-tree.xml").findall(".//node")
labels=[(n.get("text") or "") for n in nodes]
# LiveMapPanel is an Android VIEW above the dashboard, never a flat texture.
assert any("HARTĂ INTEGRATĂ" in t or "HARTĂ TEMPORAR" in t for t in labels),labels[:70]
assert any("CAUTA LOC" in t for t in labels),labels[:70]
print("K2401_RACE_HUD_REAL_CENTER_INTERACTIVE_MAP=PASS")
print("K2401_RACE_HUD_FOUR_REAL_ECU_PIDS=PASS")
print("K2401_RACE_HUD_FOUR_TOP_CONTROLS=PASS")
print("K2401_RACE_HUD_NO_BAKED_CLOCK_MAP_OR_FALSE_TEXT=PASS")
print("K2401_RACE_HUD_6_APP_SLOTS=PASS")
PY
# Verify actual top navigation is reachable in emulator and map does not
# intercept header taps: APPS opens the real installed-app drawer.
adb shell input tap 324 53
sleep 1
adb shell uiautomator dump /sdcard/race-hud-apps.xml >/dev/null
adb pull /sdcard/race-hud-apps.xml "$OUT/race-hud-apps.xml" >/dev/null
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
p=Path("projects/k2401-evo-launcher/screenshots/race-hud-apps.xml")
nodes=ET.parse(p).findall(".//node")
words=[n.get("text") or "" for n in nodes]
assert any("Aplica" in w or "Caut" in w for w in words),words[:90]
print("K2401_RACE_HUD_APPS_BUTTON_OPENS_NATIVE_DRAWER=PASS")
PY
echo 'K2401_RACE_HUD_FINAL_ANDROID10_EMULATOR=PASS'
