#!/usr/bin/env python3
"""Pixel-level Azure/Android10 gate for theme #02: no central fake ECU UI.

Actual device capture must show the precise photographic source in the center.
Clock, RPM, coolant, media and trims are drawn natively OUTSIDE this region.
This verifies the approved omission of ECU/ABS/Doors/Airbag without OCR.
"""
from pathlib import Path
from PIL import Image,ImageChops,ImageStat,ImageFilter
ROOT=Path(__file__).resolve().parents[1]
photo=ROOT/"app/src/main/assets/skins/clean/skin_01.webp"
screen=ROOT/"screenshots/skin_1.png"
with Image.open(photo) as p, Image.open(screen) as s:
    assert p.size==(2560,1440),("Photo resolution",p.size)
    assert s.size==(1280,720),("Emulator resolution",s.size)
    image=p.convert("RGB").resize((1280,720),Image.Resampling.LANCZOS)
    captured=s.convert("RGB")
    # The center must contain only the car/road, no opaque status panel.
    central=(455,255,820,600)
    delta=ImageChops.difference(image.crop(central),captured.crop(central))
    max_error=max(ImageStat.Stat(delta).mean)
    if max_error>13:
        raise AssertionError(
           f"THEME_02_CENTRE_STATUS_PANEL_OR_IMAGE_MISMATCH mean={max_error:.2f}")
    # Confirm texture, not a blurry monochrome rectangle painted over the car.
    source_crop=image.crop(central)
    variance=sum(ImageStat.Stat(source_crop).var)/3
    edge_variance=sum(ImageStat.Stat(source_crop.filter(ImageFilter.FIND_EDGES)).var)/3
    if variance<45 or edge_variance<12:
        raise AssertionError(
           f"THEME_02_PHOTO_NOT_DETAILED variance={variance:.1f} edges={edge_variance:.1f}")
    print(f"K2401_THEME_02_PHOTO_ONLY_CENTRE=PASS error={max_error:.2f} var={variance:.2f} edge={edge_variance:.2f}")
