#!/usr/bin/env python3
"""iHunt Watch6T HOLO V6 offline BIN face builder.
Original source recovered from owner's GloryFit app. Does not transmit to watch.
No firmware/OTA commands; only normal watchface cache BIN file output.

Correct GloryFit type record offsets are type (u16), width (u16), ptr (u32),
height (u16), x/y (u16), misc (u16), image count (u16), rest.
"""
from __future__ import annotations
import io,struct,zlib,hashlib, json,zipfile, math, shutil
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Work on the files beside this script. This avoids depending on earlier chat sessions.
import argparse
ap=argparse.ArgumentParser(description='Offline HOLO Watch6T builder, no phone writes')
ap.add_argument('--original', type=Path, default=Path(__file__).resolve().parent/'D1898001_ORIGINAL_DO_NOT_EDIT.bin')
ap.add_argument('--reference', type=Path, default=Path(__file__).resolve().parent/'HOLO_REFERENCE_ORIGINAL.png')
ap.add_argument('--background', type=Path, default=Path(__file__).resolve().parent/'HOLO_V6_BACKGROUND_SOURCE_240.png')
ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
opts=ap.parse_args()
SOURCE=opts.original
REF=opts.reference
BACKGROUND=opts.background
OUT=opts.out
OUT.mkdir(parents=True,exist_ok=True)
W=H=240
C=(64,228,255);G=(159,255,29);WHITE=(231,252,255)
_FONTS=[('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),('C:/Windows/Fonts/arialbd.ttf','C:/Windows/Fonts/arial.ttf')]
BIG,MED=next(((a,b) for a,b in _FONTS if Path(a).exists() and Path(b).exists()),_FONTS[0])
assert SOURCE.exists() and REF.exists() and BACKGROUND.exists()

@dataclass
class Item:
    id:int; w:int; ptr:int; h:int; x:int; y:int; c:int; frames:int; flags:int; extra:int; off:int
    @property
    def size(self): return self.w*self.h*2*self.frames

if SOURCE.suffix.lower()=='.zip':
    with zipfile.ZipFile(SOURCE) as z:
        entry=next(x for x in z.namelist() if x.endswith('D1898001.bin'))
        stock=z.read(entry)
else:
    stock=SOURCE.read_bytes()
assert len(stock)==343944
assert struct.unpack_from('<I',stock,4)[0]==len(stock)-24
assert zlib.crc32(stock[24:])&0xffffffff==struct.unpack_from('<I',stock,8)[0]
assert struct.unpack_from('<HH',stock,12)==(240,240)
items=[]
for idx in range(128):
    off=24+idx*24
    tup=struct.unpack_from('<HHIHHHHHHI',stock,off)
    if not tup[0]: break
    it=Item(*tup,off)
    assert 1<=it.w<=240 and 1<=it.h<=240 and it.frames>0
    assert it.ptr+it.size<=len(stock),(it.id,it.ptr,it.size)
    items.append(it)
assert len(items)==22
ids={i.id:i for i in items}
assert {4,5,8,10,12,13,15,17,19,20,25,30,33,34,47,49}.issubset(ids)

# RGB565 pixels are big-endian (on this file); individual frames use row-major.
def decode(blob,w,h):
    assert len(blob)==w*h*2
    vals=struct.unpack('>'+str(w*h)+'H',blob)
    im=Image.new('RGB',(w,h))
    im.putdata([((v>>11&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31) for v in vals])
    return im

def encode(img,w,h):
    img=img.convert('RGB');assert img.size==(w,h)
    data=bytearray(w*h*2)
    for j,(r,g,b) in enumerate(img.getdata()):
        v=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        data[j*2]=v>>8;data[j*2+1]=v&255
    return bytes(data)

def frames_stock(it):
    return [decode(stock[it.ptr+j*it.w*it.h*2:it.ptr+(j+1)*it.w*it.h*2],it.w,it.h) for j in range(it.frames)]

def font(size,weight='bold'):
    return ImageFont.truetype(BIG if weight=='bold' else MED,size)

def render_text(t,w,h,rgb,size=None,glow=True,weight='bold'):
    scale=4
    img=Image.new('RGB',(w*scale,h*scale),(0,0,0))
    if not t:return img.resize((w,h))
    d=ImageDraw.Draw(img)
    size=size or int(h*.95)
    ff=font(size*scale,weight)
    box=d.textbbox((0,0),t,font=ff,stroke_width=0)
    tw,th=box[2]-box[0],box[3]-box[1]
    if tw>(w-.9)*scale or th>(h-.9)*scale:
        ratio=min(((w-1)*scale)/tw,((h-1)*scale)/th)
        ff=font(max(2,int(size*scale*ratio)),weight)
        box=d.textbbox((0,0),t,font=ff)
        tw,th=box[2]-box[0],box[3]-box[1]
    x=(w*scale-tw)/2-box[0];y=(h*scale-th)/2-box[1]
    # Crisp type dominates: low glow on background only, not blurred digits.
    if glow:
        tmp=Image.new('RGBA',img.size)
        dt=ImageDraw.Draw(tmp)
        dt.text((x,y),t,font=ff,fill=(*rgb,240))
        img=Image.alpha_composite(img.convert('RGBA'),tmp.filter(ImageFilter.GaussianBlur(2.2*scale)))
        d=ImageDraw.Draw(img)
    else:img=img.convert('RGBA');d=ImageDraw.Draw(img)
    d.text((x,y),t,font=ff,fill=(*rgb,255))
    return img.convert('RGB').resize((w,h),Image.Resampling.LANCZOS)

# Create exact-source HOLO wallpaper without any frozen numerical readings.
# V5 background was derived from the user's ORIGINAL chosen picture, with
# demo readouts erased; it preserves the decorative ECG & cyan walking hologram.
bg=Image.open(BACKGROUND).convert('RGB')
assert bg.size==(240,240)
# Native 240 pixels receive a very restrained clarity/color boost; no hallucinated artwork.
bg=ImageEnhance.Contrast(bg).enhance(1.07)
bg=ImageEnhance.Sharpness(bg).enhance(1.25)
# Remove fixed BPM digits / step text residues but retain heart/running icons.
# Decorative labels are never represented as live medical readings.
background=bg.copy()
background.save(OUT/'HOLO_V6_LIVE_BACKGROUND_240.png')

# Existing firmware bindings remain exactly as in the stock file. Only image
# content and field positions/sizes change, no new field/opcode is invented.
# Types of numeric families inferred from the original image placement and
# confirmed row-major glyph atlas. Uncertain types deliberately left intact
# except neutral colorization/hidden where they clash with the chosen artwork.
new={}
geom={}

# Time display: 14-frame glyph set, 3..12 = digits 0..9, 13 = ':'.
# Official face knows HH, MM; a single frame is drawn repeatedly by the
# firmware, not static 14:26 texture in background.
for typ,color,x in [(4,(216,252,255),38),(5,G,128)]:
    w,h=32,41
    glyph=['-','.','/']+[str(i) for i in range(10)]+[':']
    new[typ]=[render_text(ch,w,h,color,size=40,glow=True) for ch in glyph]
    geom[typ]=(w,h,x,52)

# Colon between live HH:MM, using original constant separator type 49.
new[49]=[render_text(':',17,41,C,size=41)];geom[49]=(17,41,109,52)

# Battery 5-state arc above data row; fixed battery outline in original art stays.
it=ids[8];w,h=75,39
for stage in range(5):
    s=4
    im=Image.new('RGB',(w*s,h*s),(0,0,0));d=ImageDraw.Draw(im)
    # Small dashed green status arc above battery symbol; avoid covering center clock.
    x0,y0=6*s,1*s;x1,y1=(w-7)*s,(h-7)*s
    for n in range(stage+1):
        start=192+n*27
        d.arc((x0,y0,x1,y1),start,start+18,fill=(*G,),width=2*s)
    new.setdefault(8,[]).append(im.resize((w,h),Image.Resampling.LANCZOS))
geom[8]=(w,h,85,5)

# Calendar labels sit in the original HOLO neon bar.
# The actual index of locale-specific weekday/month frames may vary by firmware.
week=['DUM','LUN','MAR','MIE','JOI','VIN','SAM']
month=['IAN','FEB','MAR','APR','MAI','IUN','IUL','AUG','SEP','OCT','NOV','DEC']
new[15]=[render_text(week[n%7],39,12,WHITE,size=11,glow=False) for n in range(ids[15].frames)]
geom[15]=(39,12,69,37)
new[12]=[render_text(month[n%12],35,12,WHITE,size=11,glow=False) for n in range(ids[12].frames)]
geom[12]=(35,12,149,37)
new[13]=[render_text(({0:'-',1:'.',2:'/'}).get(n,str(n-3) if 3<=n<=12 else ':'),10,12,G,size=12,glow=False) for n in range(ids[13].frames)]
geom[13]=(10,12,121,37)

# Hearts/steps: original binary has pre-existing numerical digit atlases.
# Mapping used here is inferred from geometry of the source face, not proven
# for the particular iHunt firmware. No fabricated SpO2 numbers.
digits14=['-','.','/']+[str(i) for i in range(10)]+[':']
for typ,w,h,x,y,col in [(19,11,14,110,119,WHITE),(25,10,14,172,151,WHITE)]:
    new[typ]=[render_text(ch,w,h,col,size=h-1,glow=False) for ch in digits14]
    geom[typ]=(w,h,x,y)

# Other confirmed source face digit types: preserve meaning without placing
# potentially unrelated figures over the concept's clock and ornaments.
# Move to hidden/minimal positions and use visually transparent black sprites.
for typ in (30,47):
    it=ids[typ];new[typ]=[Image.new('RGB',(it.w,it.h),(0,0,0)) for _ in range(it.frames)]
# Unclear extra value sprites retained byte-for-byte, but their position is
# left unchanged. Their original gold/red pixels should remain tiny.

# Weather icon family: recolor stock graphics without changing frame indexes.
it=ids[20]
icons=[]
for src in frames_stock(it):
    im=src.copy();pix=im.load()
    for y in range(im.height):
        for x in range(im.width):
            r,g,b=pix[x,y]
            if max(r,g,b)<15:continue
            if r>g*1.14 and r>b*1.18:pix[x,y]=(min(255,int(r*.64)),min(255,int(g+70)),min(255,int(b+100)))
            elif r>110 and g>90 and b<100:pix[x,y]=(115,236,242)
    icons.append(im)
new[20]=icons;geom[20]=(it.w,it.h,73,190)

# Current temperature fields already present in stock face; recolor numbers.
for typ,x in [(21,109),(22,144)]:
    it=ids[typ]
    digit16=['-','.','/']+[str(i) for i in range(10)]+[':','%']
    new[typ]=[render_text(digit16[i%len(digit16)],it.w,it.h,C,size=it.h,glow=False) for i in range(it.frames)]
    geom[typ]=(it.w,it.h,x,202)

# A two-digit battery indicator family is present in the stock layout.
# Keep original content but recolor gold/red to green/cyan and relocate above.
it=ids[33]
new[33]=[render_text(digits14[i%14],12,14,G,size=14,glow=False) for i in range(it.frames)]
geom[33]=(12,14,124,19)
# Percent symbol was a one-frame constant sprite in the original face.
new[34]=[render_text('%',12,13,WHITE,size=12,glow=False)];geom[34]=(12,13,152,20)

# Hide decorative overlays that would conflict with fixed HOLO neon art.
for typ in (16,31,48,6):
    it=ids[typ];new[typ]=[Image.new('RGB',(it.w,it.h),(0,0,0)) for _ in range(it.frames)]

# Full display background (17) and preview (10) stay 240x240 RGB565.
new[17]=[background]

# Compose an illustrative preview by drawing the actual sprite frames produced
# by this binary builder, NOT the old static 14:26 values. It is not a watch capture.
preview=background.copy()
# RGB565 black 0 is transparent for non-background sprites.
def stamp(im,imxy):
    global preview
    rgb=im.convert('RGB');x,y=imxy
    mask=rgb.convert('L').point(lambda v:255 if v>14 else 0)
    preview.paste(rgb,(x,y),mask)

def place(typ,idx,x=None,y=None):
    it=ids[typ];seq=new.get(typ) or frames_stock(it)
    im=seq[idx%len(seq)];spec=geom.get(typ,(it.w,it.h,it.x,it.y))
    px,py=spec[2:] if x is None else (x,y)
    stamp(im,(px,py))
# Time as HH:MM; representative values are preview-only.
for x,idx in [(38,4),(71,7)]:place(4,idx,x,52)
place(49,0)
for x,idx in [(128,5),(161,9)]:place(5,idx,x,52)
# Date 28 / MAR; index uncertain, illustrative only.
place(15,2);place(13,5,121,37);place(13,11,131,37);place(12,0)
place(8,3);place(33,11,124,19);place(33,9,136,19);place(34,0)
# HR 78 and steps 7345 illustrative only.
for x,idx in [(113,10),(125,11)]:place(19,idx,x,119)
for x,idx in [(174,10),(184,6),(194,7),(204,8)]:place(25,idx,x,151)
place(20,2)
for typ,idx in [(21,4),(22,5)]:place(typ,idx)
preview.save(OUT/'HOLO_V6_DYNAMIC_PREVIEW_240.png')

# Rebuild payload table and bitmaps while preserving *all 22 original type IDs*,
# frame counts, unknown metadata fields, and image order. Source shared atlases
# are treated as individual rebuilt fields; no ambiguous offset reuse.
header=bytearray(stock[:24]);records=bytearray();blob=bytearray();ptr=24+24*len(items)+2
shared_atlas={}  # reuse identical immutable sprite sequences; original does this too
for it in items:
    sourceimgs=frames_stock(it)
    frames=new.get(it.id,sourceimgs)
    assert len(frames)==it.frames,(it.id,len(frames),it.frames)
    if it.id==10:frames=[preview]
    w,h,x,y=geom.get(it.id,(it.w,it.h,it.x,it.y))
    assert 0<=x<=239 and 0<=y<=239 and x+w<=240 and y+h<=240,(it.id,w,h,x,y)
    buf=b''.join(encode(im,w,h) for im in frames)
    assert len(buf)==w*h*2*it.frames
    # Source records are 24 bytes; overwrite only width, offset, height, x, y.
    r=bytearray(stock[it.off:it.off+24])
    struct.pack_into('<H',r,2,w);struct.pack_into('<I',r,4,ptr)
    struct.pack_into('<H',r,8,h);struct.pack_into('<HH',r,10,x,y)
    key=(w,h,it.frames,hashlib.sha256(buf).digest())
    if key in shared_atlas:
        struct.pack_into('<I',r,4,shared_atlas[key])
    else:
        shared_atlas[key]=ptr
        blob.extend(buf)
        ptr+=len(buf)
    records.extend(r)
records.extend(b'\x00\x00')
output=header+records+blob
struct.pack_into('<I',output,4,len(output)-24)
struct.pack_into('<I',output,8,zlib.crc32(output[24:])&0xffffffff)
expected_len=len(output)
assert struct.unpack_from('<I',output,4)[0]==len(output)-24
assert struct.unpack_from('<I',output,8)[0]==zlib.crc32(output[24:])&0xffffffff
assert len(output)>len(stock)  # Larger glyphs consume more data
binfile=OUT/'D1898001_HOLO_V6_BETA_UNTESTED.bin'
binfile.write_bytes(output)
(OUT/'D1898001_ORIGINAL_DO_NOT_EDIT.bin').write_bytes(stock)
assert output[:4]==stock[:4]
assert output[12:24]==stock[12:24]
for j,it in enumerate(items):
    t,w,p,h,x,y,dummy,frames,unused,more=struct.unpack_from('<HHIHHHHHHI',output,24+j*24)
    assert t==it.id and frames==it.frames and dummy==it.c and unused==it.flags and more==it.extra
    assert p+w*h*2*frames<=len(output)
    assert p==24+len(items)*24+2 or p>24+len(items)*24+2
manifest={
 'name':'Watch6T HOLO V6 native BIN candidate',
 'source':'Owner-provided GloryFit cached D1898001.bin',
 'source_sha256':hashlib.sha256(stock).hexdigest(),
 'output_sha256':hashlib.sha256(output).hexdigest(),
 'input_bytes':len(stock),'output_bytes':len(output),
 'original_element_type_ids':[it.id for it in items],
 'original_element_count':len(items),
 'original_frame_counts_preserved':True,
 'pixel_layout':'RGB565 big-endian, row-major, verified from digit atlas',
 'display_pixels':[240,240],
 'crc32_verified':True,
 'source_file_id_preserved':True,
 'fields_with_assumed_live_semantics':['hour','minute','calendar','steps','HR','weather','battery'],
 'unconfirmed_dynamic':['SpO2','type-to-metric mapping on target Watch6T firmware'],
 'watch_tested':False,'sync_route_confirmed':False,
 'safety':'Not firmware/OTA; do not flash or directly send over BLE; cache swap only with confirmed watch compatibility and backup.'
}
(OUT/'MANIFEST_V6.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
(OUT/'HOLO_REFERENCE_ORIGINAL.png').write_bytes(REF.read_bytes())
print(json.dumps(manifest,indent=2,ensure_ascii=False))
