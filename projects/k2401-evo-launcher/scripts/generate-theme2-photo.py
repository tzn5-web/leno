#!/usr/bin/env python3
"""Photographic layer ONLY for approved K2401 skin #02.

No numbers, text, gauges, fake status indicators or touch surfaces are ever
drawn into the photo. The actual Android UI remains vector/native and live.
Source is a permitted Unsplash image; credits are in THEME2_PHOTO_LICENSE.txt.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import io
import math
import os
from urllib.request import Request, urlopen
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter

W,H=2560,1440
SOURCE="https://images.unsplash.com/photo-1752773462774-16e3b911a90f?auto=format&fit=crop&w=3000&q=90"
CACHE=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins/photographic_sources/theme2_unsplash.jpg"

def source_image():
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    if not CACHE.exists():
        req=Request(SOURCE,headers={"User-Agent":"K2401 personal Android home launcher image renderer/1.0"})
        with urlopen(req,timeout=80) as r:
            data=r.read(18_000_001)
        if len(data)<70_000 or len(data)>18_000_000:
            raise RuntimeError("Approved licensed theme-2 photo not downloaded in full")
        Image.open(io.BytesIO(data)).verify()
        CACHE.write_bytes(data)
    data=CACHE.read_bytes()
    print("K2401_THEME02_PHOTO_SOURCE_SHA256="+hashlib.sha256(data).hexdigest())
    im=Image.open(io.BytesIO(data)).convert("RGB")
    if min(im.size)<900:raise RuntimeError("Theme 2 source is too small for UHD")
    return im

def cover(im,w,h):
    ratio=max(w/im.width,h/im.height)
    nw,nh=round(im.width*ratio),round(im.height*ratio)
    im=im.resize((nw,nh),Image.Resampling.LANCZOS)
    # centered crop preserves vehicle. No horizontal stretching.
    return im.crop(((nw-w)//2,(nh-h)//2,(nw+w)//2,(nh+h)//2))

def render():
    source=source_image()
    base=cover(source,W,H)
    image=np.asarray(base).astype("float32")
    yy,xx=np.mgrid[:H,:W]
    xx=xx/W; yy=yy/H
    # Preserve photographic detail; color grade without pixelating the vehicle.
    shadow=np.clip(.73+.35*np.exp(-((xx-.54)**2/.21+(yy-.52)**2/.27)),.65,1.08)
    image*=shadow[...,None]
    image[...,0] *= 1.05+0.11*(yy>.64) # tail/road red ambience
    image[...,1] *= .95
    image[...,2] *= 1.06+0.11*(xx>.55) # cyan shadows
    out=Image.fromarray(np.uint8(np.clip(image,0,255)),"RGB")
    # Add only abstract light rays/road motion; never copy HUD content.
    glow=Image.new("RGBA",(W,H))
    g=ImageDraw.Draw(glow,"RGBA")
    g.line([(1190,790),(280,1435)],fill=(239,41,81,76),width=18)
    g.line([(1370,790),(2190,1435)],fill=(25,181,255,73),width=18)
    g.line([(1180,820),(430,1435)],fill=(255,61,120,46),width=11)
    g.line([(1410,820),(2080,1435)],fill=(29,208,255,47),width=11)
    soft=glow.filter(ImageFilter.GaussianBlur(38))
    out=Image.alpha_composite(out.convert("RGBA"),soft)
    out=Image.alpha_composite(out,glow).convert("RGB")
    out=out.filter(ImageFilter.UnsharpMask(radius=1.3,percent=118,threshold=4))
    assert out.size==(W,H)
    return out

if __name__=="__main__":
    target=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins/clean/skin_01.webp"
    target.parent.mkdir(parents=True,exist_ok=True)
    render().save(target,"WEBP",quality=93,method=6)
    with Image.open(target) as im:
        assert im.size==(W,H)
    print("K2401_THEME02_PHOTOGRAPHIC_BACKGROUND=PASS "+str(target))
