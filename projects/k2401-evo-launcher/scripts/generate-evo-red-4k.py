#!/usr/bin/env python3
"""Generate original full-resolution 3840x2160 graphite/glass EVO scene.

No upscaling, no artificial map, no blue landscape, no baked gauges, text,
time, music, app tiles or OBD data. All interactive layers stay native Canvas.
This deterministic asset is rendered at each of the 3840x2160 source pixels.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math
import random

random.seed(2401118)
W,H,S=3840,2160,3
dest=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins/approved/evo-red-scene-3840x2160.webp"
dest.parent.mkdir(parents=True,exist_ok=True)
im=Image.new("RGB",(W,H))
d=ImageDraw.Draw(im)
# Full-resolution charcoal-to-graphite vertical field, NOT resized art.
for y in range(H):
    t=y/(H-1)
    r=round(7+9*math.sin(math.pi*t)**2)
    g=round(8+10*math.sin(math.pi*t)**2)
    b=round(11+12*math.sin(math.pi*t)**2)
    d.line((0,y,W,y),fill=(r,g,b))
# Soft, sparse red metal reflections: light only, never cyan/blue neon.
glow=Image.new("RGBA",(W,H),(0,0,0,0))
g=ImageDraw.Draw(glow,"RGBA")
for k in range(26,0,-1):
    a=round(2.1*(27-k))
    cx,cy=640*S,380*S
    rx=(220+11*k)*S;ry=(90+11*k)*S
    g.ellipse((cx-rx,cy-ry,cx+rx,cy+ry),fill=(153,24,35,a))
glow=glow.filter(ImageFilter.GaussianBlur(78))
im=Image.alpha_composite(im.convert("RGBA"),glow).convert("RGB")
d=ImageDraw.Draw(im)
def pts(seq):return [(round(x*S),round(y*S)) for x,y in seq]
def line(seq,color,width=1):
    d.line(pts(seq),fill=color,width=max(1,round(width*S)),joint="curve")
def polygon(seq,color):d.polygon(pts(seq),fill=color)
# Carbon micro-weave in genuine 4K, barely visible under the live HUD.
for y in range(110*S,H,12):
    for x in range(0,W,19):
        d.line((x,y,x+8,y+3),fill=(21,23,27),width=1)
# Technical metal rails: asymmetric specular silver and subdued red.
for side in (-1,1):
    def mirror(seq):
        return [(x if side==-1 else 1280-x,y) for x,y in seq]
    line(mirror([(0,168),(85,210),(152,210)]),(87,95,105),3.2)
    line(mirror([(0,179),(90,222),(154,222)]),(130,35,45),1.8)
    line(mirror([(0,552),(111,505),(193,505)]),(107,116,126),2.5)
    line(mirror([(0,565),(114,518),(198,518)]),(141,30,42),1.7)
    line(mirror([(0,642),(177,578),(267,578)]),(61,69,79),1.5)
# Fine metal glass cradle, keeps the center unobstructed by fake controls.
line([(427,207),(459,185),(821,185),(853,207)],(83,91,101),1.7)
line([(439,215),(467,197),(813,197),(841,215)],(143,43,53),1.1)
line([(427,450),(454,467),(826,467),(853,450)],(61,69,80),1.3)
# Subtle 3D vehicle-inspired line sculpture; NOT a photo or false sensor.
# It remains underneath the four native, translucent live instruments.
polygon([(505,353),(520,326),(552,319),(575,282),(609,270),
         (671,270),(705,282),(728,319),(760,326),(775,353),
         (769,404),(512,404)],(11,13,18))
line([(508,352),(522,326),(552,320),(575,283),(610,271),(670,271),
      (705,283),(728,320),(758,326),(773,352)],(92,100,111),2)
line([(574,284),(706,284)],(158,163,169),1.3)
line([(552,320),(728,320)],(68,76,86),1.5)
line([(508,357),(773,357)],(50,55,65),1.2)
line([(518,392),(762,392)],(77,83,91),1.4)
line([(521,365),(559,367)],(173,41,54),4)
line([(721,367),(758,365)],(173,41,54),4)
line([(550,403),(731,403)],(113,31,44),2)
# Reflective depth lines, no fictitious route or landscape.
for i in range(18):
    t=i/17
    y=438+184*t*t
    extent=90+370*t
    shade=round(25+28*(1-t))
    line([(640-extent,y),(640-extent-30*t,y+4*t)],
         (shade+9,shade+7,shade+8),.7+1.1*t)
    line([(640+extent,y),(640+extent+30*t,y+4*t)],
         (shade+9,shade+7,shade+8),.7+1.1*t)
# Original pixel-space texture and restrained metallic highlights.
for i in range(180):
    x=random.randint(410,870)*S
    y=random.randint(200,520)*S
    d.line((x,y,x+random.randint(2,13),y),
           fill=(random.randint(30,60),random.randint(30,54),random.randint(36,60)))
im.save(dest,format="WEBP",quality=94,method=6)
print("K2401_EVO_RED_4K_SCENE=PASS",dest,im.size)
