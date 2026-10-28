#!/usr/bin/env python3
"""Rebuild 21 CLEAN photo-only K2401 backgrounds from approved original images.
No screenshot UI, printed fake PIDs, apps, status text or stock car replacements
are permitted into the native dashboard background. Source assets are immutable.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import hashlib, math

ROOT=Path(__file__).resolve().parents[1]/"app/src/main/assets/skins"
OUT=ROOT/"clean"
W,H=2560,1440
# Individually audited safe car/road regions of the 21 ORIGINAL EVO designs.
# No car image on the three app-centric skins; native widgets draw actual apps.
ROI=[
(350,465,544,685),(305,65,770,333),(204,322,535,533),
(125,75,619,377),(325,55,797,352),None,(321,105,770,393),
(566,150,829,415),(446,93,787,370),(402,191,814,428),
(326,105,656,480),(352,95,846,409),(175,213,636,510),
(225,378,507,557),None,(585,252,826,458),(350,256,826,557),
(459,279,866,402),(168,164,724,592),None,(436,204,898,614)
]
PLACEMENT=[
(445,450,790,708),(304,89,785,402),(237,288,704,563),
(151,93,665,409),(326,81,868,427),None,(321,98,801,436),
(522,157,842,452),(428,91,817,451),(367,180,866,451),
(315,116,676,501),(342,92,888,442),(149,207,700,562),
(212,351,707,594),None,(566,258,855,505),(338,246,864,582),
(451,275,883,475),(155,169,744,604),None,(422,205,919,627)
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
            pix[x,y]=(int(4+8*shade+halo*a[0]*.125+road*a[0]*.021),
                      int(9+10*shade+halo*a[1]*.135+road*a[1]*.027),
                      int(18+13*shade+halo*a[2]*.15+road*a[2]*.032))
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
        # Approved Digital Dash composition: neon road converging behind the
        # actual Mitsubishi car, without a printed speed/gear/clock.
        d.line([(248,1438),(1050,974)],fill=(252,35,73,105),width=12)
        d.line([(2260,1438),(1515,974)],fill=(35,174,252,92),width=12)
        d.line([(360,1438),(1090,995)],fill=(242,60,79,38),width=27)
        d.line([(2185,1438),(1475,995)],fill=(28,180,244,32),width=27)
    return image

def scene(canvas,source,roi,dest):
    car=source.crop(roi).convert("RGB")
    x1,y1,x2,y2=(p*2 for p in dest)
    width,height=x2-x1,y2-y1
    # Diffuse atmosphere comes from the audited car crop ONLY.
    sw,sh=int(width*1.9),int(height*2.0)
    backdrop=car.resize((sw,sh),Image.Resampling.LANCZOS)
    backdrop=backdrop.filter(ImageFilter.GaussianBlur(84))
    halo=Image.new("L",(sw,sh),0)
    ImageDraw.Draw(halo).ellipse((80,55,sw-80,sh-55),fill=94)
    halo=halo.filter(ImageFilter.GaussianBlur(155))
    bx=min(W-sw,max(195,x1-(sw-width)//2))
    by=min(H-sh,max(110,y1-(sh-height)//2))
    canvas.paste(backdrop,(bx,by),halo)
    # True aspect ratio preserves wheels, panel geometry and Mitsubishi car.
    ratio=min(width/car.width,height/car.height)
    car=car.resize((max(1,int(car.width*ratio)),max(1,int(car.height*ratio))),
                   Image.Resampling.LANCZOS)
    mask=Image.new("L",car.size,0)
    inset=min(34,max(13,min(car.size)//9))
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset,inset,car.width-inset-1,car.height-inset-1),
        radius=min(65,car.width//7),fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(min(34,max(14,min(car.size)//14))))
    car=car.filter(ImageFilter.UnsharpMask(1.1,85,4))
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
            if ROI[i] is not None:
                scene(result,src,ROI[i],PLACEMENT[i])
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
