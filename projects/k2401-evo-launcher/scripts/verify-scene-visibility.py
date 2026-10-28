#!/usr/bin/env python3
"""Diagnostic: confirm the three car-centred dashboards show their original car.

The signed Android APK must render the original K2401 vehicle photography
behind native LIVE RPM and other widgets. A passed build / 21 unique PNGs
cannot detect a giant opaque native card concealing an approved car design.
Report pixel evidence from real Android 10 emulator screenshots; no OCR.
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageOps
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"
ASSETS = ROOT / "app/src/main/assets/skins"
REGIONS = {
    2: (202, 360, 518, 509),   # EVO FUTURE: rear car below large tach
    7: (655, 170, 814, 332),   # EVO GT: right side of unobscured rear car
    13: (261, 389, 506, 548),  # DIGITAL COCKPIT: actual car on road
}
rows = []
for index, rect in REGIONS.items():
    original = Image.open(ASSETS / f"skin_{index:02d}.webp").convert("RGB")
    screenshot = Image.open(SHOTS / f"skin_{index}.png").convert("RGB")
    if original.size != (1280, 720) or screenshot.size != (1280, 720):
        raise AssertionError(f"{index}: incompatible screenshot dimensions")
    difference = ImageChops.difference(original.crop(rect), screenshot.crop(rect))
    gray = ImageOps.grayscale(difference)
    histogram = gray.histogram()
    # Source compressed WEBP -> 2x sharpen -> display adds color transforms,
    # so allow generous error. This is only a car-visibility regression gate.
    coverage = sum(histogram[:64]) / max(1, gray.width * gray.height)
    rows.append((index, coverage))
    print(f"K2401_SCENE_CAR_VISIBLE skin={index:02d} source_pixel_match={coverage:.3f}")
    if coverage < 0.12:
        raise AssertionError(f"Skin {index}: approved car scene obscured; match {coverage:.3f}")
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
    "\n".join(f"skin_{i:02d} car_source_match={score:.4f}" for i, score in rows)
    + "\nALL_21_SCREENSHOTS_DISTINCT=PASS\n",
    encoding="utf-8")
print("K2401_ALL_21_VISUAL_MONTAGE=PASS", target)
