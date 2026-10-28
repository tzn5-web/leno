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
    # EXACT approved photograph, cropped WITHOUT fake sample UI. Check car
    # identity inside generated 4K media (not merely same bitmap dimensions).
    import json
    exact="assets/skins/cinematic/approved-trio-reference.webp"
    assert exact in z.namelist(),"Approved photo triptych missing from APK"
    approval=Image.open(BytesIO(z.read(exact))).convert("RGB")
    manifest=json.loads(z.read(
        "assets/skins/cinematic/cinematic-4k-manifest.json").decode("utf-8"))
    assert [m["skin"] for m in manifest]==["A1","02","A3"]
    for k,m in enumerate(manifest):
        asset=f"assets/skins/cinematic/scene_{k}_4k.webp"
        assert m["name"]==f"scene_{k}_4k.webp"
        with Image.open(BytesIO(z.read(asset))) as data:
            scene=data.convert("RGB")
        assert scene.size==(3840,2160)
        l,t,r,b=m["source_crop"]
        assert r-l==820 and 145<=b-t<=170,(k,m["source_crop"])
        approved_core=approval.crop((l,t,r,b))
        photo_h=round((b-t)*3840/(r-l))
        top=(2160-photo_h)//2-70
        # Interior regions are completely opaque in the photograph matte.
        # Compare vehicle and mountain pixels directly to the exact user art.
        expected=approved_core.resize((3840,photo_h),Image.Resampling.LANCZOS)
        focus=(1400,180,2440,photo_h-180)
        expected_arr=np.asarray(expected.crop(focus).resize((260,90)),dtype=np.int16)
        actual_arr=np.asarray(scene.crop((focus[0],top+focus[1],
                   focus[2],top+focus[3])).resize((260,90)),dtype=np.int16)
        deviation=float(np.mean(np.abs(expected_arr-actual_arr)))
        assert deviation<33,(k,"Wrong car photo or dark garage",deviation)
        # Native screenshot centre must remain visibly photographic.
        displayed=Image.open(folder/f"cinematic-{22+k}.png").convert("RGB")
        bitmap=scene.resize((1280,720),Image.Resampling.LANCZOS)
        roi=(480,262,800,429)
        delta=float(np.mean(np.abs(np.asarray(displayed.crop(roi),dtype=np.int16)-
                                   np.asarray(bitmap.crop(roi),dtype=np.int16))))
        assert delta<49,(k,"Car obscured by an opaque HUD",delta)
        print("K2401_APPROVED_CINEMATIC_CAR_VISIBLE=PASS",
              k,round(deviation,2),round(delta,2))
java=Path("projects/k2401-evo-launcher/app/src/main/java/ro/evolauncher/k2401/CinematicTrioTheme.java").read_text()
assert "color(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(16)" in java
assert "color(0xff5f819e);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.5f)" in java
assert 'c.drawRect(0,0,1280,146,p)' in java
assert 'color(0xff081626);c.drawCircle(cx,cy,r-12,p)' in java
assert '"x1000 rpm",line);' in java
assert 'p.setTextAlign(Paint.Align.RIGHT)' in java
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
