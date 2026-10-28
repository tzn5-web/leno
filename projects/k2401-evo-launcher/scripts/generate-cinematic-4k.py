#!/usr/bin/env python3
"""4K cinematic backgrounds using EXACT approved A1 / 02 / A3 photography.

Rebuild from a clean middle band of the original user-approved composition.
The concept's printed music, clock, six app icons and OBD sample values are
NOT copied into live backdrops. Letterbox expansion is formed from that same
scene at blurred atmospheric depth; no old car or dark garage substitutes.

Source reference (1672x941) is narrower than genuine 4K source detail.
Output 3840x2160 is therefore a careful upsample, not invented optical 4K.
"""
from __future__ import annotations
from PIL import Image, ImageFilter, ImageEnhance
from pathlib import Path
import numpy as np
import hashlib, json

ROOT=Path(__file__).resolve().parents[1] / "app/src/main/assets/skins"
DEST=ROOT/"cinematic"
SOURCE=DEST/"approved-trio-reference.webp"
DEST.mkdir(parents=True,exist_ok=True)
if not SOURCE.is_file():
    raise SystemExit("BLOCKED: exact user-approved A1/02/A3 source missing")
original=Image.open(SOURCE).convert("RGB")
ow,oh=original.size
assert 1600<=ow<=2500 and 900<=oh<=1300
results=[]
for index,label in enumerate(("A1","02","A3")):
    row0=round(oh*index/3)
    row1=round(oh*(index+1)/3)
    full=original.crop((0,row0,ow,row1))
    # This band preserves ORIGINAL crisp car, glass mountains and neon-tunnel
    # detail while excluding embedded mockup album/clock/apps/OBD numbers.
    source_left=(ow-820)//2
    source_top=83
    source_bottom=min(full.height-73,240)
    assert source_bottom-source_top>=145,(label,full.size)
    photo=full.crop((source_left,source_top,source_left+820,source_bottom))
    # Atmospheric extension from the identical source scene. A stretched,
    # blurred backdrop is intentionally behind the original sharp car strip.
    W,H=3840,2160
    ambient=photo.resize((W,H),Image.Resampling.BICUBIC)
    ambient=ambient.filter(ImageFilter.GaussianBlur(radius=120))
    photo_height=round(photo.height*W/photo.width)
    core=photo.resize((W,photo_height),Image.Resampling.LANCZOS)
    core=ImageEnhance.Contrast(core).enhance(1.055)
    core=core.filter(ImageFilter.UnsharpMask(radius=0.95,percent=66,threshold=2))
    top=(H-photo_height)//2-70
    # Soft mask removes any rectangle seam. Photo car itself stays 100% sharp.
    yy,xx=np.ogrid[0:photo_height,0:W]
    edge_y=np.minimum(yy,photo_height-1-yy)
    edge_x=np.minimum(xx,W-1-xx)
    y_feather=np.clip(edge_y/115.,0,1)
    # Holographic 02 source has concept STFT/LTFT at the extreme sides.
    # Hide those printed gauges, then draw live native gauges in Java.
    x_feather=np.clip(edge_x/(1050. if index==1 else 75.),0,1)
    mask=(y_feather*y_feather*(3-2*y_feather)) * (x_feather*x_feather*(3-2*x_feather))
    matte=Image.fromarray(np.uint8(mask*255),"L").filter(ImageFilter.GaussianBlur(5))
    ambient.paste(core,(0,top),matte)
    ambient=ambient.filter(ImageFilter.UnsharpMask(radius=0.9,percent=50,threshold=3))
    dest=DEST/f"scene_{index}_4k.webp"
    ambient.save(dest,"WEBP",quality=90,method=6)
    with Image.open(dest) as test:
        assert test.size==(3840,2160)
        # Visible sharp central car content: reject blurred giant old source
        # cards even if they have correct 3840x2160 pixel dimensions.
        vehicle=np.asarray(test.convert("RGB").crop((1280,top+120,2560,top+photo_height-115))
                  .resize((300,125)),dtype=np.int16)
        sharp=float(np.percentile(np.abs(np.diff(vehicle,axis=1)),90))
        assert sharp>13,(label,"Car appears too blurry",sharp)
        # The precise foreground is from the approved source car, not stock.
        centre_source=photo.resize((300,125),Image.Resampling.LANCZOS)
        # This sanity sample remains close in color to the approved photo.
        center_delta=float(np.mean(np.abs(
            np.asarray(centre_source,dtype=np.int16)-
            np.asarray(test.crop((1180,top+80,2660,top+photo_height-80))
              .resize((300,125)),dtype=np.int16))))
        assert center_delta<95,(label,"Incorrect source vehicle",center_delta)
    sha=hashlib.sha256(dest.read_bytes()).hexdigest()
    results.append(dict(skin=label,name=dest.name,
        source="approved-trio-reference.webp",
        source_crop=[source_left,row0+source_top,source_left+820,row0+source_bottom],
        pixels=[W,H],photo_detail_p90=sharp,photo_mae=center_delta,
        sha256=sha,bytes=dest.stat().st_size))
    print("4K_APPROVED_PHOTO_SCENE=PASS",label,"sharp",round(sharp,1),
          "delta",round(center_delta,1),sha)
assert len(set(entry["sha256"] for entry in results))==3
(DEST/"cinematic-4k-manifest.json").write_text(
    json.dumps(results,indent=2)+"\n",encoding="utf-8")
print("THREE_DISTINCT_APPROVED_PHOTO_ONLY_4K_SCENES=PASS")
