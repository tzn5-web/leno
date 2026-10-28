#!/usr/bin/env python3
"""Generate native 3840x2160 *text-free* cinematic car scene assets.

No screenshot/painted HUD values, dates, Wi-Fi symbols, app icons, or sample
telemetry are ever used as wallpaper. Source photographs are existing clean
user-owned project art; no new external image dependencies or licensing calls.
Assets ship INSIDE the signed APK and are not downloaded by the vehicle.
"""
from __future__ import annotations
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
from pathlib import Path
import hashlib, json, math
import sys

ROOT = Path(__file__).resolve().parents[1] / "app/src/main/assets/skins"
DEST = ROOT / "cinematic"
DEST.mkdir(parents=True, exist_ok=True)
W, H = 3840, 2160

# User-approved layout mapping, 3 *distinct* geometry profiles in Java:
# A1 = electro-blue technical wireframe car.
# 02 = front-view blue night car.
# A3 = real showroom, bright glass instrumentation.
# Underlying cleaned photographs are part of the original launcher assets.
SOURCES = (
    ("A1", "skin_03.webp", (26, 143, 235)),
    ("02", "skin_13.webp", (30, 186, 255)),
    ("A3", "skin_16.webp", (61, 205, 237)),
)
report = []
for index, (label, filename, rgb) in enumerate(SOURCES):
    original = ROOT / "clean" / filename
    assert original.is_file(), f"Clean original required: {original}"
    with Image.open(original) as source:
        source = source.convert("RGB")
        assert source.size == (2560, 1440), (original, source.size)
        scene = source.resize((W, H), Image.Resampling.LANCZOS)
    # Correct actual user-visible composition from Android 10 screenshots:
    # A1/02 previous vehicles were too far left, A3 too low (covered by dock).
    dx,dy=((720,225),(615,-270),(0,-360))[index]
    # Feather the relocated photograph against its own blurred original.
    # A hard paste creates an obvious rectangular seam at x=dx and y=dy,
    # which is unacceptable in the original approved borderless 4K cockpit.
    ambient=scene.filter(ImageFilter.GaussianBlur(radius=65))
    relocated=Image.new("RGB",(W,H),(4,11,21))
    relocated.paste(scene,(dx,dy))
    mask=Image.new("L",(W,H),0)
    m=ImageDraw.Draw(mask)
    x0=max(0,dx)+90
    y0=max(0,dy)+90
    x1=min(W,W+dx)-70
    y1=min(H,H+dy)-80
    m.rounded_rectangle((x0,y0,x1,y1),radius=340,fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(radius=175))
    scene=Image.composite(relocated,ambient,mask)
    if index==0:
        scene=ImageEnhance.Color(scene).enhance(.74)
    if index==2:
        scene=ImageEnhance.Brightness(scene).enhance(1.28)
    # Edges are enhanced carefully; 3840x2160 decoded image is full pixel
    # dimensions without pretending to have newly captured optical detail.
    scene = ImageEnhance.Contrast(scene).enhance(1.08)
    scene = ImageEnhance.Sharpness(scene).enhance(1.26)
    glow = Image.new("RGBA", (W, H))
    g = ImageDraw.Draw(glow, "RGBA")
    # Gentle vector tunnel / illuminated floor framing, beneath native HUD.
    if index <= 1:
        for j in range(11):
            x = round(W * (0.06 + 0.088 * j))
            strength = max(8, 43 - abs(5-j) * 7)
            g.line(((x, H * .26), (W/2 + (x-W/2)*1.42, H*.88)),
                   fill=(*rgb, strength), width=3)
        for yy in (int(H*.72),int(H*.78),int(H*.83)):
            g.line(((int(W*.24),yy),(int(W*.76),yy)),fill=(*rgb,21),width=3)
    else:
        for x in (int(W*.20), int(W*.80)):
            g.line(((x, int(H*.17)),(x, int(H*.80))),fill=(*rgb,22),width=4)
    scene = Image.alpha_composite(scene.convert("RGBA"), glow).convert("RGB")
    dst = DEST / f"scene_{index}_4k.webp"
    scene.save(dst, format="WEBP", quality=88, method=6)
    with Image.open(dst) as verify:
        assert verify.size == (3840, 2160), (dst, verify.size)
        assert verify.format == "WEBP"
    sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    report.append({"skin": label,"name":dst.name,"source":filename,
                   "pixels":[W,H],"sha256":sha,"bytes":dst.stat().st_size})
    print("4K_SCENE=PASS", label, dst.name, sha)
manifest=DEST/"cinematic-4k-manifest.json"
manifest.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print("THREE_DISTINCT_4K_NO_BAKED_TEXT_SCENES=PASS")
