#!/usr/bin/env python3
"""Per-scene photographic image gate for original 21 Mitsubishi EVO skins.

This is an objective signal test, not a claim that an AI picture perfectly
matches artistic direction. All other app/ECU functional gates remain intact.
"""
from pathlib import Path
from PIL import Image
import hashlib
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins"
NO_PHOTO={5,14,19}
checksums=set()
reports=[]
for i in range(21):
    src=ROOT/f"skin_{i:02d}.webp"
    clean=ROOT/"clean"/f"skin_{i:02d}.webp"
    hires=ROOT/"uhd"/f"skin_{i:02d}.webp"
    assert src.is_file() and clean.is_file() and hires.is_file(),(i,"missing artwork")
    with Image.open(src) as im: assert im.size==(1280,720),(i,"source geometry")
    with Image.open(clean) as im:
        assert im.size==(2560,1440),(i,"clean image geometry")
        view=np.asarray(im.resize((1280,720),Image.Resampling.LANCZOS).convert("RGB"))
    with Image.open(hires) as im:
        assert im.size==(2560,1440),(i,"original highres backup geometry")
    checksums.add(hashlib.sha256(clean.read_bytes()).digest())
    mono=cv2.cvtColor(view,cv2.COLOR_RGB2GRAY)
    blur_sharp=float(cv2.Laplacian(mono,cv2.CV_64F).var())
    dynamic=float(np.percentile(mono,98)-np.percentile(mono,2))
    if i not in NO_PHOTO:
        # Distinguish a reconstructed car scene from a blurred gradient.
        assert blur_sharp>2.0,(i,"photo detail missing",blur_sharp)
        assert dynamic>20,(i,"car contrast missing",dynamic)
        assert clean.stat().st_size>45000,(i,"overcompressed photographic scene")
    reports.append(f"skin_{i:02d} clean_webp={clean.stat().st_size}B sharpness={blur_sharp:.2f} contrast={dynamic:.1f}")
    print("K2401_IMAGE_DETAIL_QA",reports[-1])
assert len(checksums)==21,"Duplicate or missing distinct skin backgrounds"
print("K2401_IMAGE_DETAIL_QA_ALL_21=PASS")
(ROOT.parent.parent.parent.parent/"screenshots").mkdir(parents=True,exist_ok=True)
