#!/usr/bin/env python3
"""Build 2x restored assets from exactly the 21 approved K2401 EVO screenshots.
No new car brands or layouts; source assets remain untouched. UI and OBD stay native.
"""
from pathlib import Path
from PIL import Image, ImageFilter
import hashlib

BASE = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "assets" / "skins"
DEST = BASE / "uhd"
DEST.mkdir(parents=True, exist_ok=True)

for skin in range(21):
    source = BASE / f"skin_{skin:02}.webp"
    original_data = source.read_bytes()
    with Image.open(source) as original:
        original.load()
        if original.size != (1280, 720):
            raise SystemExit(f"Unexpected source dimensions: {source}: {original.size}")
        result = original.convert("RGB")
        result = result.filter(ImageFilter.UnsharpMask(radius=0.75, percent=85, threshold=4))
        result = result.resize((2560, 1440), Image.Resampling.LANCZOS)
        result = result.filter(ImageFilter.UnsharpMask(radius=1.25, percent=110, threshold=3))
        target = DEST / source.name
        result.save(target, "WEBP", quality=96, method=6)
    with Image.open(target) as inspect:
        assert inspect.size == (2560, 1440)
    assert source.read_bytes() == original_data, "Approved source was unexpectedly changed"
    print(f"{skin:02d} 2560x1440 {target.stat().st_size} bytes sha256={hashlib.sha256(target.read_bytes()).hexdigest()[:12]}")

assert len(list(DEST.glob("skin_??.webp"))) == 21
print("K2401_APPROVED_21_UHD_RESOURCES=PASS")
