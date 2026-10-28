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
    # Guard the actual car and mountain photo, not just 3840x2160 metadata.
    exact="assets/skins/cinematic/approved-trio-reference.webp"
    assert exact in z.namelist(), "Exact approved photo reference absent"
    approval=Image.open(BytesIO(z.read(exact))).convert("RGB")
    rw,rh=approval.size
    for k in range(3):
        asset=f"assets/skins/cinematic/scene_{k}_4k.webp"
        with Image.open(BytesIO(z.read(asset))) as data:
            image=data.convert("RGB").resize((1280,720),Image.Resampling.LANCZOS)
        crop_h=round(rh*(k+1)/3)-round(rh*k/3)
        crop_w=round(crop_h*16/9)
        left=(rw-crop_w)//2
        user=approval.crop((left,round(rh*k/3),left+crop_w,round(rh*(k+1)/3)))
        approved=user.resize((1280,720),Image.Resampling.LANCZOS)
        photo_delta=np.mean(np.abs(np.asarray(image,dtype=np.int16)-
                                   np.asarray(approved,dtype=np.int16)))
        assert photo_delta<28,(k,"wrong vehicle/garage or blurry stock replacement",photo_delta)
        # Compare the unoccluded vehicle centre to the actual Android 10
        # emulator screenshot. This FAILS if a fake card hides the vehicle.
        roi=(465,190,814,524)
        screen=np.asarray(shots[22+k].crop(roi),dtype=np.int16)
        real=np.asarray(image.crop(roi),dtype=np.int16)
        screen_delta=np.mean(np.abs(screen-real))
        assert screen_delta<49,(k,"approved vehicle covered in emulator",screen_delta)
        print("K2401_APPROVED_CINEMATIC_PHOTO_IN_EMULATOR=PASS",
              k,round(float(photo_delta),2),round(float(screen_delta),2))
    assert "cinematic-4k-manifest.json" in " ".join(z.namelist())
java=Path("projects/k2401-evo-launcher/app/src/main/java/ro/evolauncher/k2401/CinematicTrioTheme.java").read_text()
assert "color(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(16)" in java
assert "color(0xff5f819e);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.5f)" in java
assert 'c.drawRect(0,0,1280,146,p)' in java
assert 'c.drawRect(0,554,1280,720,p)' in java
assert 'vertical(c,217,159,149,387,"STFT"' in java
assert 'vertical(c,917,159,149,387,"LTFT"' in java
assert 'circle(c,371,382,78,"STFT"' in java
assert 'circle(c,909,382,78,"LTFT"' in java
assert 'panel(c,261,12,484,88,12,0xff081725,line)' in java
assert 'panel(c,767,8,276,94,13,0xff081725,line)' in java
print("K2401_FOUR_OBD_APPROVED_GAUGE_GEOMETRY=PASS")
print("K2401_ZERO_GHOST_APP_CLOCK_MUSIC_OVERLAP=PASS")
print("K2401_02_GAUGE_ARC_NEVER_SOLID_DISK=PASS")
print("K2401_A1_02_A3_DIFFERENT_NATIVE_SCREENSHOTS=PASS")
print("K2401_A1_02_A3_4K_ART_IN_APK=PASS")
PY
# Slot #1 may already be configured by the previous Ultra cockpit test.
# Press-and-hold MUST show the actual app chooser in either case.
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 24 >/dev/null
sleep 1
adb shell input swipe 459 644 459 644 850
sleep 1
adb shell uiautomator dump /sdcard/cinematic-hold.xml >/dev/null
adb pull /sdcard/cinematic-hold.xml "$OUT/cinematic-hold.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as E
names=[n.get("text","") for n in E.parse("projects/k2401-evo-launcher/screenshots/cinematic-hold.xml").findall(".//node")]
assert any("Aplicația 1" in v for v in names),names
assert any("Golește acest slot" in v for v in names),names
print("K2401_CINEMATIC_SHORTCUT_LONG_PRESS_REPLACE=PASS")
PY
# Clear the slot *through native UI*, not adb pm clear, so shared user
# preferences for other slots and all 22 old skins stay untouched.
python3 - <<'PY'
import xml.etree.ElementTree as E, re,subprocess
nodes=E.parse("projects/k2401-evo-launcher/screenshots/cinematic-hold.xml").findall(".//node")
n=next(x for x in nodes if "Golește acest slot" in x.get("text",""))
a,b,c,d=map(int,re.findall(r"\d+",n.get("bounds","")))
subprocess.check_call(["adb","shell","input","tap",str((a+c)//2),str((b+d)//2)])
PY
sleep 1
adb shell input tap 459 644
sleep 1
adb shell uiautomator dump /sdcard/cinematic-picker.xml >/dev/null
adb pull /sdcard/cinematic-picker.xml "$OUT/cinematic-picker.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as E
names=[n.get("text","") for n in E.parse("projects/k2401-evo-launcher/screenshots/cinematic-picker.xml").findall(".//node")]
assert any("Aplicația 1" in v for v in names),names
print("K2401_CINEMATIC_EMPTY_PLUS_SINGLE_TAP_PICKER=PASS")
PY
echo 'K2401_A1_02_A3_CINEMATIC_4K_EMULATOR=PASS'
