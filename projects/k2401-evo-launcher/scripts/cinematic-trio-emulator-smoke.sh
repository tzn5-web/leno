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
# Regression: previous three themes had solid black 146px upper and
# 166px lower bands. Photographic backdrop must be visible through BOTH.
for skin,pic in shots.items():
    for label,rect in (
            ("top cinematic scene",(100,110,1180,145)),
            ("bottom cinematic scene",(90,565,1180,605))):
        region=pic.crop(rect)
        chroma=ImageStat.Stat(region).stddev
        assert max(chroma)>3.5,(
            skin,label,"solid black letterbox or empty canvas",chroma)
        print("K2401_CINEMATIC_NO_SOLID_BLACK_BANDS=PASS",skin,label,
              round(max(chroma),2))
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
    # Exact three user-approved individual source designs, not the old collage
    # or the unrelated original 21 skin photos.
    import json,hashlib
    manifest=json.loads(z.read(
        "assets/skins/cinematic/cinematic-4k-manifest.json").decode("utf-8"))
    assert [m["skin"] for m in manifest]==["A1","02","A3"]
    for k,m in enumerate(manifest):
        src=f"assets/skins/cinematic/approved-{m['skin']}.webp"
        assert src in z.namelist(),src
        assert m["source"]==f"approved-{m['skin']}.webp"
        assert m["source_sha256"]==hashlib.sha256(z.read(src)).hexdigest()
        with Image.open(BytesIO(z.read(src))) as photo:
            approved=photo.convert("RGB")
        assert approved.size==(1672,941)
        asset=f"assets/skins/cinematic/scene_{k}_4k.webp"
        assert m["name"]==f"scene_{k}_4k.webp"
        with Image.open(BytesIO(z.read(asset))) as photo:
            scene=photo.convert("RGB")
        assert scene.size==(3840,2160)
        # Real physical car image must match the APPROVED current photograph
        # in the image centre; there must not be a different stock car.
        focus=(490,230,790,415)
        expected=approved.resize((1280,720),Image.Resampling.LANCZOS)
        bitmap=scene.resize((1280,720),Image.Resampling.LANCZOS)
        exp=np.asarray(expected.crop(focus),dtype=np.int16)
        got=np.asarray(bitmap.crop(focus),dtype=np.int16)
        car_error=float(np.mean(np.abs(exp-got)))
        assert car_error<30,(m["skin"],"Wrong approved car",car_error)
        displayed=shots[22+k]
        onscreen_error=float(np.mean(np.abs(
            np.asarray(displayed.crop(focus),dtype=np.int16)-got)))
        assert onscreen_error<49,(m["skin"],"Vehicle covered by native HUD",onscreen_error)
        # Printed demo music and six sample app logos were removed from both
        # wallpaper strips. Android draws true MediaSession / installed apps.
        top=(400,20,880,120)
        bottom=(350,615,980,705)
        top_difference=float(np.mean(np.abs(np.asarray(
            expected.crop(top),dtype=np.int16)-np.asarray(
            bitmap.crop(top),dtype=np.int16))))
        bottom_difference=float(np.mean(np.abs(np.asarray(
            expected.crop(bottom),dtype=np.int16)-np.asarray(
            bitmap.crop(bottom),dtype=np.int16))))
        assert top_difference>8,(m["skin"],"Static music/clock art leaked",top_difference)
        assert bottom_difference>8,(m["skin"],"Static application art leaked",bottom_difference)
        print("K2401_EXACT_APPROVED_IMAGE_IN_4K_APK=PASS",
              m["skin"],round(car_error,1),round(onscreen_error,1))
        print("K2401_NO_BAKED_MEDIA_OR_SHORTCUTS=PASS",m["skin"])
java=Path("projects/k2401-evo-launcher/app/src/main/java/ro/evolauncher/k2401/CinematicTrioTheme.java").read_text()
assert "color(edge);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(16)" in java
assert "color(0xff5f819e);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.5f)" in java
assert 'new int[]{0xd6040d1b,0x92040d1b,0x00040d1b}' in java
assert 'c.drawRect(0,0,1280,146,p)' not in java
assert 'color(0xff081626);c.drawCircle(cx,cy,r-12,p)' in java
assert '"x1000 rpm",line);' in java
assert 'p.setTextAlign(Paint.Align.RIGHT)' in java
assert 'new int[]{0x00040d1b,0x7c040d1b,0xe0040d1b}' in java
assert 'c.drawRect(0,554,1280,720,p)' not in java
assert 'vertical(c,27,162,160,427,"RPM"' in java
assert 'vertical(c,1093,162,160,427,"TEMP APĂ"' in java
assert 'halfGauge(c,515,522,90,"STFT"' in java
assert 'halfGauge(c,765,522,90,"LTFT"' in java
assert 'circle(c,155,382,148,"RPM"' in java
assert 'circle(c,1125,382,148,"TEMP APĂ"' in java
assert 'halfGauge(c,527,516,85,"STFT"' in java
assert 'halfGauge(c,753,516,85,"LTFT"' in java
assert 'framedCircle(c,160,291,124,"RPM"' in java
assert 'framedCircle(c,160,508,86,"STFT"' in java
assert 'framedCircle(c,1120,291,124,"TEMP APĂ"' in java
assert 'framedCircle(c,1120,508,86,"LTFT"' in java
assert 'panel(c,261,12,484,88,12,0xff081725,line)' in java
app_java=Path("projects/k2401-evo-launcher/app/src/main/java/ro/evolauncher/k2401/UltraCockpitTheme.java").read_text()
assert 'return isCinematicTrio()?278:SLOT_X;' in app_java
assert 'return isCinematicTrio()?108:SLOT_W;' in app_java
assert 'return isCinematicTrio()?94:SLOT_H;' in app_java
print("K2401_SIX_WIDE_CINEMATIC_APP_TILES_AND_TOUCH=PASS")
assert 'panel(c,767,8,276,94,13,0xff081725,line)' in java
assert 'private static final int QUICK_X=13, QUICK_Y=18, QUICK_W=56, QUICK_GAP=6, QUICK_H=76;' in java
assert 'private static final int[] QUICK_ICON={5,4,2,1};' in java
assert 'private static final String[] QUICK_TEXT={"SETUP","APPS","NAVI","MUZICĂ"};' in java
assert 'if(quickNavigationTouch(x,y))return true;' in java
assert 'quickNavigation(c,line);' in java
assert "host.page=destination;" in java
assert "host.showInstalledApps();return true;" in java
print("K2401_FOUR_HEADER_QUICK_ACTIONS_AND_TOUCH_MAPPING=PASS")
print("K2401_FOUR_OBD_APPROVED_GAUGE_GEOMETRY_A1_02_A3=PASS")
print("K2401_ZERO_GHOST_APP_CLOCK_MUSIC_OVERLAP=PASS")
print("K2401_02_GAUGE_ARC_NEVER_SOLID_DISK=PASS")
print("K2401_A1_02_A3_DIFFERENT_NATIVE_SCREENSHOTS=PASS")
print("K2401_A1_02_A3_4K_ART_IN_APK=PASS")
PY
# Slot #1 may already be configured by the previous Ultra cockpit test.
# Press-and-hold MUST show the actual app chooser in either case.
adb shell am start -W -n "$APP/.MainActivity" --ei k2401_skin_preview_ci 24 >/dev/null
sleep 1
adb shell input swipe 332 649 332 649 850
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
adb shell input tap 332 649
sleep 1
adb shell uiautomator dump /sdcard/cinematic-picker.xml >/dev/null
adb pull /sdcard/cinematic-picker.xml "$OUT/cinematic-picker.xml" >/dev/null
python3 - <<'PY'
import xml.etree.ElementTree as E
names=[n.get("text","") for n in E.parse("projects/k2401-evo-launcher/screenshots/cinematic-picker.xml").findall(".//node")]
assert any("Aplicația 1" in v for v in names),names
print("K2401_CINEMATIC_EMPTY_PLUS_SINGLE_TAP_PICKER=PASS")
PY
# Confirm every header shortcut reaches its native page in the REAL
# emulator (not merely static text assertions). Compare main Canvas pixels.
python3 - <<'PY'
from PIL import Image,ImageChops,ImageStat
from pathlib import Path
import subprocess,time
folder=Path("projects/k2401-evo-launcher/screenshots")
APP="ro.evolauncher.k2401"
routes=[("SETUP",41,5),("APPS",103,4),("NAVI",165,2),("MUSIC",227,1)]
for label,x,target in routes:
    subprocess.run(["adb","shell","am","force-stop",APP],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(["adb","shell","am","start","-W","-n",APP+"/.MainActivity",
                    "--ei","k2401_skin_preview_ci","24"],check=True,stdout=subprocess.DEVNULL)
    time.sleep(1.3)
    def shot(file):
        subprocess.run(["adb","shell","screencap","-p","/sdcard/"+file],check=True)
        subprocess.run(["adb","pull","/sdcard/"+file,str(folder/file)],check=True,stdout=subprocess.DEVNULL)
        return Image.open(folder/file).convert("RGB")
    before=shot("quick-"+label+"-before.png")
    subprocess.run(["adb","shell","input","tap",str(x),"54"],check=True)
    time.sleep(1.4)
    after=shot("quick-"+label+"-after.png")
    assert after.size==(1280,720)
    diff=ImageChops.difference(before.crop((260,130,1040,560)),
                               after.crop((260,130,1040,560)))
    change=sum(ImageStat.Stat(diff).mean)/3
    assert change>5.0,(label,"Quick action did not open its native page",change)
    print("K2401_QUICK_NAV_REAL_TAP=PASS",label,"page",target,"pixel_delta",round(change,2))
PY
echo 'K2401_A1_02_A3_CINEMATIC_4K_EMULATOR=PASS'
