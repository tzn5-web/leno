#!/usr/bin/env python3
"""Actual Android 10 signed-APK framebuffer audit of skins 21..28.

Does not use OCR, generated mockups, or invented OBD readings. Pixel checks
cannot prove subjective fidelity; the original 1280x720 screenshots are kept
for human review. No screenshot is silently marked as visually approved.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
from PIL import Image, ImageDraw, ImageFont, ImageStat

folder=Path(sys.argv[1] if len(sys.argv)>1 else "k2401-glass-hud-signed-screens")
assert folder.is_dir(),folder
base=Path(__file__).resolve().parents[1]
source=base/"app/src/main/java/ro/evolauncher/k2401"
race=(source/"RaceHudFinalTheme.java").read_text()
ultra=(source/"UltraCockpitTheme.java").read_text()
cinematic=(source/"CinematicTrioTheme.java").read_text()
fx=(source/"GlassHudFx.java").read_text()
assert "GlassHudFx.dial" in race and "GlassHudFx.dial" in ultra
assert "GlassHudFx.dial" in cinematic and "GlassHudFx.glassPanel" in fx
assert "GlassHudFx.backdrop(c,21)" in ultra
assert "GlassHudFx.backdrop(c,27)" in race
assert "no duplicate top-right clock" in ultra
assert "Float.isFinite(value)" in fx and "Float.isFinite(fraction)" in cinematic
assert "selected_skin_v2" in (source/"SkinEngine.java").read_text()
release=base/"app/build/outputs/apk/release/app-release.apk"
assert release.is_file(),release
with zipfile.ZipFile(release) as z:
    asset="assets/skins/approved/evo-red-scene-3840x2160.webp"
    assert asset in z.namelist()
    with Image.open(io.BytesIO(z.read(asset))) as im:
        assert im.size==(3840,2160),im.size
    for i in range(21):
        assert f"assets/skins/skin_{i:02d}.webp" in z.namelist()
print("K2401_GLASS_HUD_SIGNED_TRUE_4K_AND_21_LEGACY_SKINS=PASS")
views={}
report={}
for skin in range(21,29):
    file=folder/f"skin-{skin}.png"
    assert file.is_file(),file
    raw=file.read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        rgb=im.convert("RGB")
    assert rgb.size==(1280,720),(skin,rgb.size)
    contrast=ImageStat.Stat(rgb).stddev
    assert max(contrast)>12,(skin,"blank or unreadable framebuffer",contrast)
    # Exclude live map, media and real installed-app icons from color grading:
    # those external apps are allowed to contain blue. Audit the HUD field.
    blue=red=total=0
    for y in range(185,560,4):
        for x in range(24,1256,4):
            if skin in (25,26) and 395<x<885:continue
            r,g,b=rgb.getpixel((x,y))
            if b>100 and b>r*1.42 and b>g*1.19:blue+=1
            if r>95 and r>g*1.35 and r>b*1.16:red+=1
            total+=1
    blue_fraction=blue/max(1,total)
    assert blue_fraction<.10,(skin,"blue/cyan still dominates glass HUD",blue_fraction)
    # Real native gauges must contain legible bright vector labels.
    left,right={
        21:((135,280,420,490),(900,280,1190,490)),
        22:((32,190,188,548),(1092,190,1250,548)),
        23:((30,245,280,520),(1000,245,1250,520)),
        24:((40,175,290,375),(990,175,1240,375)),
        25:((55,245,355,475),(925,245,1225,475)),
        26:((45,230,370,445),(915,230,1235,445)),
        27:((55,245,355,475),(925,245,1225,475)),
        28:((70,210,375,480),(905,210,1210,480)),
    }[skin]
    for side,box in (("RPM",left),("coolant",right)):
        crop=rgb.crop(box)
        light=sum(1 for r,g,b in crop.getdata() if min(r,g,b)>145)
        assert light>70,(skin,side,"missing legible light text",light)
    if skin==27:
        projection=rgb.crop((480,265,800,440))
        assert max(ImageStat.Stat(projection).stddev)>8, "holographic centre is blank"
    report[str(skin)]={
        "resolution":"1280x720",
        "blue_dominance_fraction":round(blue_fraction,5),
        "red_pixel_count":red,
        "rgb_stddev":[round(v,2) for v in contrast],
        "sha256":hashlib.sha256(raw).hexdigest(),
        "subjective_reference_match":"not established"
    }
    views[skin]=rgb
    print(f"K2401_SIGNED_GLASS_HUD_FRAME=PASS skin={skin} blue_fraction={blue_fraction:.4f}")
# Full-native-resolution comparison sheet. Labels are outside screenshots.
sheet=Image.new("RGB",(2560,4*752),(8,9,12))
d=ImageDraw.Draw(sheet)
font=ImageFont.load_default()
for idx,skin in enumerate(range(21,29)):
    x=(idx%2)*1280;y=(idx//2)*752
    d.text((x+18,y+9),f"K2401 SKIN {skin} | ACTUAL SIGNED ANDROID 10 EMULATOR",
           fill=(226,222,218),font=font)
    sheet.paste(views[skin],(x,y+32))
montage=folder/"K2401-HOLOGRAPHIC-21-28-ANDROID10.jpg"
sheet.save(montage,quality=93,subsampling=0)
(folder/"holographic-audit.json").write_text(
    json.dumps({"status":"automated visual checks passed",
                "human_fidelity_review":"required",
                "skins":report},indent=2),encoding="utf-8")
print("K2401_GLASS_HUD_ALL_EIGHT_SIGNED_SCREENSHOTS_AUDITED=PASS",montage)
