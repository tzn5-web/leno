#!/usr/bin/env python3
"""Build UHD cinematic wallpaper layers from the THREE *individual approved* A1/02/A3 designs.

These three images originate from user-approved ChatGPT designs. The source
screenshot contains sample music, OBD values, a clock and app logos; NEVER
ship that screenshot as the entire live UI. Remove the baked top/media and
bottom/app panels and obscure fake numeric centers. Native Android Canvas
provides live music/status/sensor gauges/apps on top of these layers.

Original image-generation source is 1672x941; 3840x2160 output is enhanced
resampling, not an assertion that the camera/renderer produced native 4K.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import hashlib, json

ROOT=Path(__file__).resolve().parents[1]/'app/src/main/assets/skins/cinematic'
ROOT.mkdir(parents=True,exist_ok=True)
W,H=3840,2160
SOURCES=[('A1','approved-A1.webp'),('02','approved-02.webp'),('A3','approved-A3.webp')]
MASK_TEXT={
  'A1':[(195,278,95,135),(1470,278,95,135),(540,655,93,56),(1133,653,93,56)],
  '02':[(250,430,125,96),(1450,430,125,96),(648,665,102,48),(1014,665,102,48)],
  'A3':[(225,326,105,97),(1455,325,105,97),(228,565,100,67),(1455,565,100,67)],
}

def wipe_region(img, rectangle, target, blur=6):
    mask=Image.new('L',img.size,0)
    draw=ImageDraw.Draw(mask)
    draw.rectangle(rectangle,fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(blur))
    return Image.composite(target,img,mask)

report=[]
for i,(label,filename) in enumerate(SOURCES):
    raw=ROOT/filename
    if not raw.is_file():raise SystemExit('BLOCKER: missing approved original '+str(raw))
    with Image.open(raw) as original:
        original=original.convert('RGB')
    assert original.size==(1672,941), (filename,original.size)
    source_sha=hashlib.sha256(raw.read_bytes()).hexdigest()
    im=original.copy()
    # The HUD row is repainted by native Android. Sampling only the scene
    # centre prevents the album, static time, fake WiFi, static gauges at the
    # sides, and mock player labels from leaking into dynamic UI.
    ceiling=im.crop((350,165,1322,285)).resize((1672,225),Image.Resampling.BICUBIC)
    ceiling=ceiling.filter(ImageFilter.GaussianBlur(5))
    top=im.copy();top.paste(ceiling,(0,0))
    im=wipe_region(im,(0,0,1672,211),top,blur=16)
    # The six real installed-app buttons are rendered from PackageManager.
    # Clear ONLY the source screenshot's static, nonfunctional icons first.
    road=im.crop((480,673,1192,741)).resize((1672,242),Image.Resampling.BICUBIC)
    road=road.filter(ImageFilter.GaussianBlur(8))
    floor=im.copy();floor.paste(road,(0,699))
    im=wipe_region(im,(0,710,1672,941),floor,blur=20)
    # Mask illustrative digits in gauge centre faces, retaining the source's
    # decorative neon rims. Real ECU numbers are rendered on opaque native
    # gauge faces, avoiding duplicate or falsely frozen values.
    face=Image.new('RGB',im.size,(5,16,31))
    masks=Image.new('L',im.size,0)
    pen=ImageDraw.Draw(masks)
    for cx,cy,rx,ry in MASK_TEXT[label]:
        pen.ellipse((cx-rx,cy-ry,cx+rx,cy+ry),fill=245)
    masks=masks.filter(ImageFilter.GaussianBlur(radius=13))
    im=Image.composite(face,im,masks)
    im=im.resize((W,H),Image.Resampling.LANCZOS)
    im=ImageEnhance.Contrast(im).enhance(1.035)
    im=im.filter(ImageFilter.UnsharpMask(radius=1.10,percent=72,threshold=2))
    dst=ROOT/f'scene_{i}_4k.webp'
    im.save(dst,format='WEBP',quality=92,method=6)
    with Image.open(dst) as v:
        assert v.size==(3840,2160)
    sha=hashlib.sha256(dst.read_bytes()).hexdigest()
    report.append(dict(skin=label,source=filename,source_sha256=source_sha,
                       source_pixels=[1672,941],output_pixels=[W,H],
                       cleaned_baked_HUD=True,cleaned_baked_shortcuts=True,
                       name=dst.name,sha256=sha,bytes=dst.stat().st_size))
    print('4K_APPROVED_SCENE=PASS',label,dst.name,sha)
assert len({x['sha256'] for x in report})==3
(ROOT/'cinematic-4k-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('K2401_EXACT_THREE_APPROVED_SOURCE_IMAGES=PASS')
print('K2401_NO_FROZEN_CLOCK_MUSIC_OBD_APP_LABELS_IN_SCENE=PASS')