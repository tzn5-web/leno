#!/usr/bin/env python3
"""Generate three exact-layout 4K scenes from the USER-APPROVED triptych.

Source artwork is versioned with the app:
  assets/skins/cinematic/approved-trio-reference.webp
NO substitute stock car, wrong showroom or geometry-shift/blur from unrelated
original skins. Dynamic live overlay cards are fully opaque where the approved
concept contains sample songs, weather, date and app icons. This protects real
ECU and Android data from any baked-in labels.

Source reference width is 1672px across three stacked panels. 3840x2160
output is a high-quality upscale, NOT native 4K original optical detail.
"""
from __future__ import annotations
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path
import json, hashlib
import numpy as np

ASSETS=Path(__file__).resolve().parents[1] / "app/src/main/assets/skins"
DEST=ASSETS/"cinematic"
REF=DEST/"approved-trio-reference.webp"
DEST.mkdir(parents=True,exist_ok=True)
if not REF.is_file(): raise SystemExit("BLOCKED: exact approved A1/02/A3 triptych missing")
with Image.open(REF) as raw:
    approved=raw.convert("RGB")
W,H=approved.size
assert W>=1600 and H>=900,(W,H)
report=[]
for index,label in enumerate(("A1","02","A3")):
    y0=round(H*index/3)
    y1=round(H*(index+1)/3)
    crop_h=y1-y0
    crop_w=round(crop_h*16/9)
    x0=(W-crop_w)//2
    # Zero geometry distortion, and preserve the EXACT user-selected blue
    # garage, holographic Lancer and bright glass mountain showroom.
    photo=approved.crop((x0,y0,x0+crop_w,y1))
    # LANCZOS preserves original UI-size detail; sharpening is gentle.
    photo=photo.resize((1920,1080),Image.Resampling.LANCZOS)
    photo=ImageEnhance.Contrast(photo).enhance(1.065)
    photo=photo.filter(ImageFilter.UnsharpMask(radius=1.0,percent=68,threshold=2))
    photo=photo.resize((3840,2160),Image.Resampling.LANCZOS)
    photo=photo.filter(ImageFilter.UnsharpMask(radius=0.85,percent=52,threshold=3))
    name=f"scene_{index}_4k.webp"
    dest=DEST/name
    photo.save(dest,format="WEBP",quality=92,method=6)
    with Image.open(dest) as check:
        assert check.size==(3840,2160) and check.format=="WEBP"
        sample=np.asarray(check.resize((320,180)),dtype=np.int16)
        detail=float(np.percentile(np.abs(np.diff(sample,axis=1)),90))
        assert detail>=9,(label,detail,"Source picture too soft or dark")
        # Reject generic blurry stock scenes: the decoded native centre must
        # resemble the approved 3-panel reference (prior build lacked this).
        reference=np.asarray(approved.crop((x0,y0,x0+crop_w,y1))
            .resize((320,180),Image.Resampling.LANCZOS),dtype=np.float32)
        delta=float(np.mean(np.abs(reference-sample)))
        assert delta<24,(label,delta,"Photo altered relative to user approval")
    sha=hashlib.sha256(dest.read_bytes()).hexdigest()
    report.append(dict(skin=label,name=name,source="approved-trio-reference.webp",
        crop=[x0,y0,x0+crop_w,y1],pixels=[3840,2160],detail_p90=detail,
        approved_difference_mae=delta,sha256=sha,bytes=dest.stat().st_size))
    print("4K_APPROVED_SCENE=PASS",label,"detail",round(detail,2),"delta",round(delta,2),sha)
assert len({entry["sha256"] for entry in report})==3
(DEST/"cinematic-4k-manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print("THREE_EXACT_USER_APPROVED_CINEMATIC_BACKGROUNDS=PASS")
