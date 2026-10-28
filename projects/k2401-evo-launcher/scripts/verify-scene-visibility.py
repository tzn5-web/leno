#!/usr/bin/env python3
"""Diagnostic: confirm the three car-centred dashboards show their original car.

The signed Android APK must render the original K2401 vehicle photography
behind native LIVE RPM and other widgets. A passed build / 21 unique PNGs
cannot detect a giant opaque native card concealing an approved car design.
Report pixel evidence from real Android 10 emulator screenshots; no OCR.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
ASSETS = ROOT / "app/src/main/assets/skins"
# Per-theme, pixel-level car-visibility regression gate. Both images come
# from the actual signed-build source and Android emulator: no OCR or mock
# screenshot substitution. A dark opaque widget over a car must FAIL even
# when twenty-one unique screenshots exist.
import runpy
positions=runpy.run_path(str(ROOT/"scripts/build-clean-scenes.py"))["PLACEMENT"]
assert len(positions)==21
rows=[]
for index,rect in enumerate(positions):
    if rect is None:
        continue  # 3 app-centric themes correctly use a real Android app grid.
    clean=Image.open(ASSETS/"clean"/f"skin_{index:02d}.webp").convert("RGB")
    screenshot=Image.open(SHOTS/f"skin_{index}.png").convert("RGB")
    assert clean.size==(2560,1440) and screenshot.size==(1280,720)
    clean=clean.resize((1280,720),Image.Resampling.LANCZOS)
    reference=clean.crop(rect).getdata()
    display=screenshot.crop(rect).getdata()
    visible=eligible=0
    for a,b in zip(reference,display):
        high=max(a);low=min(a)
        if high>65 and high-low>18:
            eligible+=1
            if max(abs(a[0]-b[0]),abs(a[1]-b[1]),abs(a[2]-b[2]))<42:
                visible+=1
    if eligible<250:
        raise AssertionError(f"Skin {index}: car image lacks photographic detail")
    ratio=visible/eligible
    rows.append((index,ratio))
    print(f"K2401_CAR_VISIBILITY skin={index:02d} source_pixels_visible={ratio:.3f}")
    if ratio<0.32:
        raise AssertionError(f"Skin {index}: live UI hides approved vehicle (ratio {ratio:.3f})")
print("K2401_ALL_18_APPROVED_CAR_SCENES_VISIBILITY=PASS")
# Compact evidence of *real* emulator output, not mockup-only thumbnails.
names = ["EVO DIGITAL DASH", "EVO CLASSIC", "EVO FUTURE", "EVO GAUGE PRO",
         "EVO MULTI INFO", "EVO APPS CENTER", "EVOLUTION NIGHT", "EVO GT",
         "EVO RED FRONT", "LANCER MOUNTAIN", "EVO SPEED", "EVO SUNSET",
         "LANCER HERO", "DIGITAL COCKPIT", "TECH GRID", "GAUGES FOCUS",
         "LANCER SHOWROOM", "MINIMAL SPORT", "CAR STATUS",
         "APP LAUNCHER", "PERFORMANCE"]
W, H, COLS = 320, 199, 5
contact = Image.new("RGB", (W * COLS, H * 5), "#080e19")
draw = ImageDraw.Draw(contact)
digests = set()
for i in range(21):
    path = SHOTS / f"skin_{i}.png"
    data = path.read_bytes()
    digests.add(hashlib.sha256(data).digest())
    with Image.open(path) as picture:
        if picture.size != (1280, 720):
            raise AssertionError(f"Wrong skin dimensions {i}: {picture.size}")
        tile = picture.convert("RGB").resize((320, 180), Image.Resampling.LANCZOS)
        x, y = (i % COLS) * W, (i // COLS) * H
        contact.paste(tile, (x, y))
        draw.text((x + 5, y + 181), f"{i+1:02d} {names[i]}", fill="#e5eefb")
assert len(digests) == 21, "The emulator must render 21 distinct skins"
target = SHOTS / "k2401-21-native-skins-montage.jpg"
contact.save(target, quality=92, subsampling=0)
(SHOTS / "k2401-visibility-report.txt").write_text(
    "\n".join(f"skin_{i:02d} foreground_visible={score:.4f}" for i, score in rows)
    + "\nALL_21_SCREENSHOTS_DISTINCT=PASS\n",
    encoding="utf-8")
print("K2401_ALL_21_VISUAL_MONTAGE=PASS", target)
