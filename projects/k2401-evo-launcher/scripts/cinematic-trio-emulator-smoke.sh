#!/usr/bin/env bash
set -euo pipefail
APP=ro.evolauncher.k2401
OUT=projects/k2401-evo-launcher/screenshots
mkdir -p "$OUT"
adb shell wm size 1280x720
adb shell wm density 160
adb shell pm path "$APP" >/dev/null
for skin in 22 23 24; do
  adb shell am force-stop "$APP"
  adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci "$skin" > "$OUT/cinematic-$skin-launch.txt"
  sleep 2
  adb shell pidof "$APP" >/dev/null
  adb shell screencap -p "/sdcard/cinematic-$skin.png"
  adb pull "/sdcard/cinematic-$skin.png" "$OUT/cinematic-$skin.png" >/dev/null
  echo "K2401_NEW_CINEMATIC_THEME_CAPTURED=PASS id=$skin"
done
python3 - <<'PY'
from pathlib import Path
from PIL import Image,ImageStat
from zipfile import ZipFile
from io import BytesIO
from itertools import combinations
import numpy as np
folder=Path("projects/k2401-evo-launcher/screenshots")
shots={}
for idx in (22,23,24):
    pic=Image.open(folder/f"cinematic-{idx}.png").convert("RGB")
    assert pic.size==(1280,720),(idx,pic.size)
    assert ImageStat.Stat(pic).stddev[1]>15,(idx,"blank image")
    shots[idx]=pic
for i,j in combinations((22,23,24),2):
    delta=np.mean(np.abs(np.asarray(shots[i],dtype=np.int16)-np.asarray(shots[j],dtype=np.int16)))
    assert delta>5.0,(i,j,delta,"duplicate visual geometry")
with ZipFile("projects/k2401-evo-launcher/app/build/outputs/apk/debug/app-debug.apk") as z:
    for k in range(3):
        asset=f"assets/skins/cinematic/scene_{k}_4k.webp"
        assert asset in z.namelist(),asset
        with Image.open(BytesIO(z.read(asset))) as pic:
            assert pic.size==(3840,2160),(asset,pic.size)
    assert "assets/skins/cinematic/cinematic-4k-manifest.json" in z.namelist()
print("K2401_A1_02_A3_DIFFERENT_NATIVE_SCREENSHOTS=PASS")
print("K2401_A1_02_A3_4K_ART_IN_APK=PASS")
PY
# The most recently selected theme is 24 A3. Shortcut position #1 is
# native and persistent, not a hardcoded screenshot or a seventh button.
adb shell input tap 459 644
sleep 1
adb shell uiautomator dump /sdcard/cinematic-picker.xml >/dev/null
adb pull /sdcard/cinematic-picker.xml "$OUT/cinematic-picker.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as E
names=[n.get("text","") for n in E.parse("projects/k2401-evo-launcher/screenshots/cinematic-picker.xml").findall(".//node")]
assert any("Aplicația 1" in v for v in names),names
print("K2401_CINEMATIC_SHORTCUT_TAP_PICKER=PASS")
PY
adb shell input keyevent BACK
sleep 1
adb shell input swipe 459 644 459 644 800
sleep 1
adb shell uiautomator dump /sdcard/cinematic-hold.xml >/dev/null
adb pull /sdcard/cinematic-hold.xml "$OUT/cinematic-hold.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as E
texts=[n.get("text","") for n in E.parse("projects/k2401-evo-launcher/screenshots/cinematic-hold.xml").findall(".//node")]
assert any("Aplicația 1" in v for v in texts),texts
print("K2401_CINEMATIC_SHORTCUT_LONG_PRESS_PICKER=PASS")
PY
echo 'K2401_A1_02_A3_CINEMATIC_4K_EMULATOR=PASS'
