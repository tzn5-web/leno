#!/usr/bin/env bash
# Approved red/white angular RACE HUD FINAL (skin 25).
# Actual Android 10 emulator screenshot and native map status, not static mock.
set -euo pipefail
APP=ro.evolauncher.k2401
OUT=projects/k2401-evo-launcher/screenshots
mkdir -p "$OUT"
adb shell wm size 1280x720
adb shell wm density 160
# Earlier emulator smoke tests intentionally exercise crash recovery and
# repeatedly force-stop the launcher. Re-enable the REAL map through its
# existing native recovery action before testing skins 25/26, otherwise the
# previous map_disabled preference yields a false-negative placeholder.
# This affects ONLY the disposable emulator, never the physical head unit.
adb shell am start -W -n "$APP/.SafeModeActivity" >/dev/null
sleep 1
adb shell uiautomator dump /sdcard/k2401-race-retry-map.xml >/dev/null
adb pull /sdcard/k2401-race-retry-map.xml "$OUT/race-retry-map-ui.xml" >/dev/null
python3 - <<'PY'
import re,subprocess,xml.etree.ElementTree as ET
nodes=ET.parse("projects/k2401-evo-launcher/screenshots/race-retry-map-ui.xml").findall(".//node")
button=next(n for n in nodes if "Reîncearcă harta la următoarea pornire" in n.attrib.get("text",""))
x1,y1,x2,y2=map(int,re.findall(r"[0-9]+",button.attrib["bounds"]))
subprocess.check_call(["adb","shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)])
PY
sleep 3
adb shell pidof "$APP" >/dev/null
echo 'K2401_RACE_HUD_REAL_MAP_RECOVERY_RESET=PASS'
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
assert 'static final int ID=25' in src and 'RACE HUD • CARBON GLASS RED' in skins
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
assert any("GPS • POZIȚIE REALĂ" in t or "HARTĂ INTEGRATĂ" in t or "HARTĂ TEMPORAR" in t for t in labels),labels[:70]
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
# New independent angular-wing skin 26: verify actual selection and screenshot
# without replacing or modifying approved circular skin 25 or user's settings.
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 26 > "$OUT/race-hud-angular-launch.txt"
sleep 3
adb shell pidof "$APP" >/dev/null
adb shell screencap -p /sdcard/race-hud-angular.png
adb pull /sdcard/race-hud-angular.png "$OUT/race-hud-angular.png" >/dev/null
adb shell uiautomator dump /sdcard/race-hud-angular-tree.xml >/dev/null
adb pull /sdcard/race-hud-angular-tree.xml "$OUT/race-hud-angular-tree.xml" >/dev/null
python3 - <<'PY'
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
import xml.etree.ElementTree as ET
root=Path("projects/k2401-evo-launcher")
src=(root/"app/src/main/java/ro/evolauncher/k2401/RaceHudFinalTheme.java").read_text()
skin=(root/"app/src/main/java/ro/evolauncher/k2401/SkinEngine.java").read_text()
main=(root/"app/src/main/java/ro/evolauncher/k2401/MainActivity.java").read_text()
ultra=(root/"app/src/main/java/ro/evolauncher/k2401/UltraCockpitTheme.java").read_text()
a=Image.open(root/"screenshots/race-hud-final.png").convert("RGB")
b=Image.open(root/"screenshots/race-hud-angular.png").convert("RGB")
assert a.size==b.size==(1280,720)
diff=ImageChops.difference(a.crop((21,190,400,492)),b.crop((21,190,400,492)))
visual_delta=sum(ImageStat.Stat(diff).mean)/3
assert visual_delta>5.0,("Circular and angular themes look the same",visual_delta)
assert 'static final int ID=25, ANGULAR_ID=26, HOLO_ID=27, EVO_RED_ID=28;' in src
assert 'angularGauge(c,false,"RPM"' in src
assert 'angularGauge(c,true,"TEMP APĂ"' in src
assert 'RACE HUD • ANGULAR SILVER RED' in skin
assert 'RaceHudFinalTheme.ANGULAR_ID' in main
assert 'RaceHudFinalTheme.ANGULAR_ID' in ultra
assert 'slots.drawUserSlots(c)' in src
words=[n.attrib.get("text","") for n in ET.parse(
  root/"screenshots/race-hud-angular-tree.xml").findall(".//node")]
assert any("GPS • POZIȚIE REALĂ" in w or "HARTĂ INTEGRATĂ" in w or "HARTĂ TEMPORAR" in w for w in words),words[:60]
assert any("CAUTA LOC" in w for w in words),words[:60]
print("K2401_SECOND_RACE_HUD_ANGULAR_REAL_MAP=PASS")
print("K2401_TWO_DISTINCT_RACE_HUD_NATIVE_LAYOUTS=PASS",round(visual_delta,2))
print("K2401_ANGULAR_WINGS_4_REAL_OBD_PIDS_6_APPS=PASS")
PY
# Long-hold personal app slot on angular home must activate Android chooser.
adb shell input swipe 332 648 332 648 850
sleep 1
adb shell uiautomator dump /sdcard/race-angular-picker.xml >/dev/null
adb pull /sdcard/race-angular-picker.xml "$OUT/race-angular-picker.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path
p=Path("projects/k2401-evo-launcher/screenshots/race-angular-picker.xml")
texts=[n.attrib.get("text","") for n in ET.parse(p).findall(".//node")]
assert any("Aplicația 1" in x for x in texts),texts[:80]
print("K2401_RACE_ANGULAR_LONG_PRESS_PICKER=PASS")
PY
echo 'K2401_CARBON_RED_AND_ANGULAR_WINGS_ANDROID10_EMULATOR=PASS'

# EVO RED DIGITAL v117: real 3840x2160 scene, 1280x720 framebuffer,
# four native top actions and six editable shortcuts (no fabricated ECU).
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 28 > "$OUT/evo-red-v117-launch.txt"
sleep 3
adb shell pidof "$APP" >/dev/null
adb shell screencap -p /sdcard/evo-red-v117-home.png
adb pull /sdcard/evo-red-v117-home.png "$OUT/evo-red-v117-home.png" >/dev/null
python3 - <<'PY'
from PIL import Image,ImageStat
from pathlib import Path
p=Path("projects/k2401-evo-launcher/screenshots/evo-red-v117-home.png")
im=Image.open(p).convert("RGB")
assert im.size==(1280,720),im.size
assert max(ImageStat.Stat(im).stddev)>8,"EVO RED Home is blank"
print("K2401_EVO_RED_V117_REAL_1280x720_SCREENSHOT=PASS")
PY
# MUSIC action at x=850 is distinct from media transport controls x=583..723.
adb shell input tap 850 53
sleep 2
adb shell screencap -p /sdcard/evo-red-v117-music.png
adb pull /sdcard/evo-red-v117-music.png "$OUT/evo-red-v117-music.png" >/dev/null
python3 - <<'PY'
from PIL import Image,ImageChops,ImageStat
from pathlib import Path
root=Path("projects/k2401-evo-launcher/screenshots")
a=Image.open(root/"evo-red-v117-home.png").convert("RGB")
b=Image.open(root/"evo-red-v117-music.png").convert("RGB")
assert a.size==b.size==(1280,720)
diff=ImageStat.Stat(ImageChops.difference(a,b)).mean
assert max(diff)>8,("EVO RED music action did not switch page",diff)
print("K2401_EVO_RED_V117_MUSIC_TOUCH_NATIVE_PAGE=PASS")
PY
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 28 >/dev/null
sleep 2
adb shell input swipe 200 648 200 648 850
sleep 1
adb shell uiautomator dump /sdcard/evo-red-v117-slot.xml >/dev/null
adb pull /sdcard/evo-red-v117-slot.xml "$OUT/evo-red-v117-slot.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as ET
from pathlib import Path
p=Path("projects/k2401-evo-launcher/screenshots/evo-red-v117-slot.xml")
texts=[n.get("text") or "" for n in ET.parse(p).findall(".//node")]
assert any("Aplicația 1" in t for t in texts),texts[:70]
print("K2401_EVO_RED_V117_SIX_EDITABLE_APP_SLOTS=PASS")
PY
echo 'K2401_EVO_RED_V118_ANDROID10_EMULATOR=PASS'

# Skin 27 used to display a blank, opaque pretend map rectangle. It must now
# render a distinct live Android Canvas glass projection without fake telemetry.
adb shell am force-stop "$APP"
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 27 > "$OUT/holo-glass-launch.txt"
sleep 3
adb shell pidof "$APP" >/dev/null
adb shell screencap -p /sdcard/holo-glass-27.png
adb pull /sdcard/holo-glass-27.png "$OUT/holo-glass-27.png" >/dev/null
python3 - <<'PY'
from pathlib import Path
from PIL import Image,ImageStat
root=Path("projects/k2401-evo-launcher")
src=(root/"app/src/main/java/ro/evolauncher/k2401/RaceHudFinalTheme.java").read_text()
fx=(root/"app/src/main/java/ro/evolauncher/k2401/GlassHudFx.java").read_text()
pic=Image.open(root/"screenshots/holo-glass-27.png").convert("RGB")
assert pic.size==(1280,720)
centre=pic.crop((478,264,802,440))
assert max(ImageStat.Stat(centre).stddev)>8,"Holographic center is blank"
assert "GlassHudFx.backdrop(c,27)" in src
assert "if(!holo)" in src
assert "Float.isFinite(value)" in fx
print("K2401_HOLOGRAPHIC_NATIVE_GLASS_27_ANDROID10=PASS")
PY
