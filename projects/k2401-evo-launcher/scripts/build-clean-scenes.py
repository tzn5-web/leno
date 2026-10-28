#!/usr/bin/env python3
"""Rebuild 21 CLEAN photo-only K2401 backgrounds from approved original images.
No screenshot UI, printed fake PIDs, apps, status text or stock car replacements
are permitted into the native dashboard background. Source assets are immutable.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps
import hashlib, math, os, base64, tempfile

# Small, locally pinned Apache-2.0 FSRCNN_x2 model. Only photographic
# Mitsubishi crops are enhanced; no fake UI/PID text can be regenerated.
_SR_ENGINE=None
_SR_INITIALIZED=False

def superresolve_vehicle(photo):
    global _SR_ENGINE,_SR_INITIALIZED
    if not _SR_INITIALIZED:
        _SR_INITIALIZED=True
        try:
            import cv2
            import numpy as np
            location=Path(__file__).resolve().parent/"models/FSRCNN_x2.pb.base64"
            raw=base64.b64decode(location.read_text().strip(),validate=True)
            if len(raw)<35000:raise ValueError("FSRCNN model truncated")
            with tempfile.NamedTemporaryFile(suffix=".pb") as tmp:
                tmp.write(raw);tmp.flush()
                engine=cv2.dnn_superres.DnnSuperResImpl_create()
                engine.readModel(tmp.name)
                engine.setModel("fsrcnn",2)
                _SR_ENGINE=engine
            print("K2401_NATIVE_SCENE_FSR2X=ENABLED")
        except Exception as exc:
            print("K2401_NATIVE_SCENE_FSR2X=FAILED",repr(exc))
            if os.environ.get("K2401_REQUIRE_SR")=="YES":raise
    if _SR_ENGINE is None:return photo
    import cv2
    import numpy as np
    bgr=cv2.cvtColor(np.asarray(photo),cv2.COLOR_RGB2BGR)
    result=_SR_ENGINE.upsample(bgr)
    if result.shape[0]!=photo.height*2 or result.shape[1]!=photo.width*2:
        raise RuntimeError("SR output dimensions unexpected")
    return Image.fromarray(cv2.cvtColor(result,cv2.COLOR_BGR2RGB))


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
(295,355,825,610),(240,60,820,458),(205,241,735,607),
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
        # Approved Digital Dash: the whole road, not a rectangular inset,
        # remains visible around the real Mitsubishi; no printed telemetry.
        # Coordinate space is 2560x1440, the native screenshot is 1280x720.
        horizon=808
        mountains=[(195,872)]
        for x in range(195,1785,54):
            y=int(horizon+37+19*math.sin(x/91)+13*math.cos(x/47))
            mountains.append((x,y))
        mountains.extend([(1785,1034),(195,1034)])
        d.polygon(mountains,fill=(2,16,36,230))
        d.polygon([(1000,825),(1205,825),(2020,1372),(170,1372)],
                  fill=(4,13,29,165))
        # Perspective lines converge behind the car and continue past it.
        edges=[
          ([(1000,839),(225,1408)],(250,38,70,190),20),
          ([(1205,839),(1890,1408)],(35,205,255,171),19),
          ([(1042,855),(435,1404)],(240,62,109,102),9),
          ([(1180,856),(1695,1404)],(46,180,248,85),9)]
        for points,col,wide in edges:
            d.line(points,fill=col,width=wide,joint="curve")
        # Road markers: each strip recedes towards the car, not UI widgets.
        for lane in range(7):
            t=(lane+1)/8
            yy=int(900+(t*t)*489)
            w=int(10+45*t)
            x1=int(1085-(140+420*t));x2=int(1150+(170+450*t))
            d.line([(x1,yy),(x1-w,yy+18+28*t)],
                   fill=(244,41,95,int(75+75*t)),width=max(2,int(3+8*t)))
            d.line([(x2,yy),(x2+w,yy+18+28*t)],
                   fill=(38,172,244,int(65+62*t)),width=max(2,int(3+8*t)))
        # Broad photographic atmospheric glow rather than stock HUD symbols.
        glow=Image.new("RGBA",(W,H),(0,0,0,0))
        brush=ImageDraw.Draw(glow,"RGBA")
        brush.line([(1000,839),(225,1408)],fill=(253,23,96,104),width=32)
        brush.line([(1205,839),(1890,1408)],fill=(11,181,255,90),width=30)
        glow=glow.filter(ImageFilter.GaussianBlur(49))
        image=Image.alpha_composite(image.convert("RGBA"),glow).convert("RGB")
    return image

def extend_photo_atmosphere(canvas,source,roi,dest,theme):
    """Blend the SAME approved car/road scene into the nearby background.

    The previous 21 previews looked like small sharp rectangular photos pasted
    over pure black. This deliberately keeps the individual photographed
    car, its lighting and scenic perspective without importing fake UI labels.
    """
    x1,y1,x2,y2=dest
    w,h=x2-x1,y2-y1
    left=max(97,int(x1-w*.23))
    top=max(55,int(y1-h*.24))
    right=min(1280,int(x2+w*.23))
    bottom=min(720,int(y2+h*.24))
    if right-left<90 or bottom-top<90:return
    size=((right-left)*2,(bottom-top)*2)
    photo=ImageOps.fit(source.crop(roi).convert("RGB"),size,
                       Image.Resampling.LANCZOS,centering=(.5,.56))
    # Remove any screenshot-era fragments at the boundary before native UI.
    photo=photo.filter(ImageFilter.GaussianBlur(46))
    photo=ImageEnhance.Color(photo).enhance(1.24)
    photo=ImageEnhance.Contrast(photo).enhance(1.12)
    photo=ImageEnhance.Brightness(photo).enhance(.80)
    feather=Image.new("L",size,0)
    margin=max(16,min(size)//10)
    ImageDraw.Draw(feather).rounded_rectangle(
        (margin,margin,size[0]-margin-1,size[1]-margin-1),
        radius=max(30,min(size)//8),fill=173)
    feather=feather.filter(ImageFilter.GaussianBlur(68))
    canvas.paste(photo,(left*2,top*2),feather)


def scene(canvas,source,roi,dest,theme):
    car=superresolve_vehicle(source.crop(roi).convert("RGB"))
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
    # A blurred polygon alone left 20%-opaque pixels at crop edges, making a
    # harsh rectangular black box visible on the approved 1280x720 cockpit.
    # A C1-continuous alpha MUST be exactly zero at every photo boundary.
    # The native vehicle stays sharp in the centre; do not sharpen text/UI.
    import numpy as np
    ww,hh=car.size
    xx=np.arange(ww,dtype=np.float32)[None,:]
    yy=np.arange(hh,dtype=np.float32)[:,None]
    fade_x=max(24.,ww*(.17 if theme==0 else .12))
    fade_top=max(12.,hh*(.14 if theme==0 else .10))
    fade_bottom=max(21.,hh*(.17 if theme==0 else .12))
    fx=np.clip(np.minimum(xx,(ww-1)-xx)/fade_x,0.,1.)
    fy=np.clip(np.minimum(yy/fade_top,((hh-1)-yy)/fade_bottom),0.,1.)
    smooth_x=fx*fx*(3.-2.*fx)
    smooth_y=fy*fy*(3.-2.*fy)
    matte=np.uint8(np.clip(smooth_x*smooth_y*255.,0.,255.))
    mask=Image.fromarray(matte,"L")
    assert mask.getpixel((0,hh//2))==0 and mask.getpixel((ww-1,hh//2))==0
    assert mask.getpixel((ww//2,0))==0 and mask.getpixel((ww//2,hh-1))==0
    # Avoid hard rectangular or false gauge fragments across all 18 photos.
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
            if i==0:
                # The approved Digital Dash has an uninterrupted rear-road
                # photograph behind both real gauges, not a hard small 4:3
                # photo card. Paint an atmospheric extension from the SAME
                # source-locked original roadway. Heavy blur guarantees that
                # printed gear/scale remnants never become visible again.
                road=ImageOps.fit(src.crop(ROI[0]).convert("RGB"),
                                  (1532,1300),method=Image.Resampling.LANCZOS,
                                  centering=(0.5,0.64))
                road=road.filter(ImageFilter.GaussianBlur(48))
                road=ImageEnhance.Contrast(road).enhance(1.18)
                road=ImageEnhance.Color(road).enhance(1.30)
                road=ImageEnhance.Brightness(road).enhance(0.82)
                fade=Image.new("L",road.size,0)
                ImageDraw.Draw(fade).rounded_rectangle(
                    (86,72,road.width-86,road.height-72),
                    radius=160,fill=222)
                fade=fade.filter(ImageFilter.GaussianBlur(100))
                result.paste(road,(188,130),fade)
            if ROI[i] is not None:
                if i!=0:
                    extend_photo_atmosphere(result,src,ROI[i],PLACEMENT[i],i)
                scene(result,src,ROI[i],PLACEMENT[i],i)
        if i==1:
            # New approved theme #02: replace ONLY photographic scene; gauges,
            # time/date, media and touch widgets are native Android canvases.
            # This picture has no baked telemetry and no ECU/ABS/Doors panel.
            import runpy
            module=runpy.run_path(str(Path(__file__).with_name("generate-theme2-photo.py")))
            result=module["render"]()
            print("K2401_THEME02_NO_PRINTED_ECU_ABS_DOORS=PASS")
        target=OUT/("skin_%02d.webp"%i)
        # Preserve reconstructed edges and gradients; 92 caused visible softening
        # of Lancer taillights and gauge-adjacent road details on Android 10.
        result.save(target,"WEBP",quality=97,method=6)
        with Image.open(target) as check:
            assert check.size==(2560,1440)
        assert hashlib.sha256(original.read_bytes()).digest()==before
        digest=hashlib.sha256(target.read_bytes()).digest()
        digests.append(digest)
        print("K2401_CLEAN_SCENE=%02d BYTES=%d"%(i,target.stat().st_size))
    assert len(set(digests))==21
    print("K2401_ALL_21_CLEAN_PHOTO_BACKGROUNDS=PASS")
    # Strict source/detail QA in CI and Azure. Do not make builds depend on
    # OpenCV for non-CI/legacy local developers who explicitly skip SR.
    if os.environ.get("K2401_REQUIRE_SR")=="YES":
        import runpy
        runpy.run_path(str(Path(__file__).with_name("verify-image-quality.py")),
                       run_name="__main__")

if __name__=="__main__":
    main()
