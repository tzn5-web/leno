#!/usr/bin/env python3
"""Rebuild 21 CLEAN photo-only K2401 backgrounds from approved original images.
No screenshot UI, printed fake PIDs, apps, status text or stock car replacements
are permitted into the native dashboard background. Source assets are immutable.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import hashlib, math

ROOT=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins"
OUT=ROOT/"clean"
W,H=2560,1440
# Individually audited safe car/road regions of the 21 ORIGINAL EVO designs.
# No car image on the three app-centric skins; native widgets draw actual apps.
ROI=[
(260,471,625,693),(305,65,770,333),(212,348,535,533),
(125,75,619,377),(325,55,797,352),None,(321,105,770,393),
(580,150,829,352),(446,93,787,370),(402,191,814,428),
(326,105,656,480),(352,95,846,409),(175,213,636,510),
(225,378,507,557),None,(585,252,826,458),(350,256,826,557),
(170,250,735,426),(168,164,724,592),None,(436,204,898,614)
]
PLACEMENT=[
(195,370,863,708),(240,60,820,458),(205,241,735,607),
(105,65,755,485),(240,55,910,495),None,(285,68,851,481),
(472,116,875,489),(350,50,842,457),(300,135,910,512),
(270,70,725,556),(285,52,921,502),(220,185,770,619),
(175,322,757,662),None,(510,190,924,566),(275,198,929,638),
(285,185,927,567),(120,125,754,650),None,(379,145,935,695)
]
COLORS=[(255,42,73),(245,48,68),(33,188,245),(245,54,73),
(34,198,244),(246,47,81),(243,41,72),(247,52,82),(243,49,78),
(51,205,240),(248,59,85),(246,116,73),(247,45,81),(28,188,245),
(243,45,81),(242,42,79),(47,194,235),(246,55,89),(38,205,225),
(241,46,83),(252,45,78)]

def base(i):
    a=COLORS[i]
    # Build smooth 2x background: original scene palette, no fake gauges.
    low=Image.new("RGB",(640,360))
    pix=low.load()
    focus=[.42,.55,.52,.42,.63][i%5]
    for y in range(360):
        yy=y/359
        for x in range(640):
            xx=x/639
            halo=math.exp(-(((xx-focus)/.32)**2+((yy-.62)/.47)**2)*2.1)
            road=math.exp(-((yy-.68)/.18)**2)
            shade=max(0,1-(abs(xx-.5)+abs(yy-.55))*.65)
            pix[x,y]=(int(5+11*shade+halo*a[0]*.17+road*a[0]*.04),
                      int(10+12*shade+halo*a[1]*.18+road*a[1]*.04),
                      int(19+14*shade+halo*a[2]*.18+road*a[2]*.05))
    image=low.resize((W,H),Image.Resampling.BICUBIC)
    d=ImageDraw.Draw(image,"RGBA")
    for k in range(4):
        y=(515+k*125)*2
        d.line(((196,y),(1480,y-48)),fill=(*a,22+k*5),width=2)
    for k in range(7):
        x=(175+82*k)*2
        d.line(((x,1160),(x-250,1435)),fill=(*a,31),width=3)
    d.arc((370,280,1660,1600),189,355,fill=(*a,26),width=3)
    if i==0:
        # Approved Digital Dash has a red/cyan night highway converging behind
        # the REAL Lancer, never a baked speed/gear/clock or demo widget.
        d.line([(258,1438),(1110,950)],fill=(255,36,75,140),width=13)
        d.line([(2240,1438),(1480,950)],fill=(32,185,255,125),width=13)
        d.line([(400,1438),(1150,995)],fill=(255,25,82,48),width=27)
        d.line([(2160,1438),(1470,995)],fill=(33,210,240,42),width=27)
    return image

def scene(canvas,source,roi,dest,theme):
    car=source.crop(roi).convert("RGB")
    x1,y1,x2,y2=(p*2 for p in dest)
    width,height=x2-x1,y2-y1
    # Keep all wheels/body proportions native; user-approved car imagery only.
    ratio=min(width/car.width,height/car.height)
    car=car.resize((max(1,int(car.width*ratio)),max(1,int(car.height*ratio))),
                   Image.Resampling.LANCZOS)
    # Use a blurred copy of the SAME approved scene as atmospheric fill.
    sw,sh=int(car.width*1.45),int(car.height*1.4)
    backdrop=car.resize((sw,sh),Image.Resampling.LANCZOS)
    backdrop=backdrop.filter(ImageFilter.GaussianBlur(42))
    halo=Image.new("L",(sw,sh),0)
    ImageDraw.Draw(halo).ellipse((22,22,sw-22,sh-22),fill=100)
    halo=halo.filter(ImageFilter.GaussianBlur(106))
    bx=max(96,min(W-sw,x1+(width-sw)//2))
    by=max(100,min(H-sh,y1+(height-sh)//2))
    canvas.paste(backdrop,(bx,by),halo)
    # Larger actual car while avoiding screenshot borders and ghost labels.
    car=ImageEnhance.Contrast(car).enhance(1.11)
    car=ImageEnhance.Brightness(car).enhance(1.17)
    car=car.filter(ImageFilter.UnsharpMask(radius=1.2,percent=75,threshold=3))
    mask=Image.new("L",car.size,0)
    inset=min(17,max(7,min(car.size)//25))
    if theme==0:
        # The original EVO roadway has printed gauge fragments only at
        # its top corners. Trim these diagonally, retain the entire car
        # and road instead of cutting out a tiny vehicle-only thumbnail.
        ImageDraw.Draw(mask).polygon([
            (int(car.width*.15),0),(int(car.width*.85),0),
            (car.width-1,int(car.height*.36)),
            (car.width-1,car.height-1),(0,car.height-1),
            (0,int(car.height*.36))],fill=255)
    else:
        ImageDraw.Draw(mask).rounded_rectangle(
          (inset,inset,car.width-inset-1,car.height-inset-1),
          radius=min(48,car.width//10),fill=255)
    # Feather only the crop perimeter, never the vehicle centre.
    # The old 15px transition showed a rectangular photo edge on K2401.
    mask=mask.filter(ImageFilter.GaussianBlur(52 if theme==0 else 30))
    canvas.paste(car,(x1+(width-car.width)//2,y1+(height-car.height)//2),mask)

def main():
    assert len(ROI)==len(PLACEMENT)==len(COLORS)==21
    OUT.mkdir(parents=True,exist_ok=True)
    digests=[]
    for i in range(21):
        original=ROOT/("skin_%02d.webp"%i)
        before=hashlib.sha256(original.read_bytes()).digest()
        with Image.open(original) as src:
            assert src.size==(1280,720)
            result=base(i)
            # Original illustrated palette provides soft scene continuity.
            # It is blurred beyond legibility: fake text, app icons, RPM
            # and weather cannot become readable in the CLEAN asset.
            atmosphere=src.convert("RGB").resize((W,H),Image.Resampling.LANCZOS)
            atmosphere=atmosphere.filter(ImageFilter.GaussianBlur(83))
            atmosphere=ImageEnhance.Brightness(atmosphere).enhance(0.52)
            result=Image.blend(result,atmosphere,0.62)
            if ROI[i] is not None:
                scene(result,src,ROI[i],PLACEMENT[i],i)
        target=OUT/("skin_%02d.webp"%i)
        result.save(target,"WEBP",quality=92,method=6)
        with Image.open(target) as check:
            assert check.size==(2560,1440)
        assert hashlib.sha256(original.read_bytes()).digest()==before
        digest=hashlib.sha256(target.read_bytes()).digest()
        digests.append(digest)
        print("K2401_CLEAN_SCENE=%02d BYTES=%d"%(i,target.stat().st_size))
    assert len(set(digests))==21
    print("K2401_ALL_21_CLEAN_PHOTO_BACKGROUNDS=PASS")

if __name__=="__main__":
    main()
