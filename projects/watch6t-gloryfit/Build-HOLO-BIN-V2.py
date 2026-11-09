#!/usr/bin/env python3
"""Create an OFFLINE-only HOLO RGB565 candidate by changing only the stock
240x240 preview/background image payloads (IDs 10 and 17). Leave every
sprite, element definition, asset offset, file ID and reserved header byte
untouched. Recalculate CRC32 for testing against the original file.

NOT for device flash/firmware update. No ADB, BLE or networking.
"""
import argparse, hashlib, json, math, struct, zlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

W=H=240
FONT_CANDIDATES=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','C:/Windows/Fonts/arialbd.ttf']
def font(size):
    for p in FONT_CANDIDATES:
        try:return ImageFont.truetype(p,size)
        except OSError:continue
    return ImageFont.load_default()

def parse(b):
    if len(b)<24:raise ValueError('Bad header')
    declared=struct.unpack_from('<I',b,4)[0]
    crc=struct.unpack_from('<I',b,8)[0]
    if declared!=len(b)-24:raise ValueError('Invalid source payload length')
    if (zlib.crc32(b[24:])&0xffffffff)!=crc:raise ValueError('Invalid source CRC32')
    if struct.unpack_from('<HH',b,12)!=(W,H):raise ValueError('Wrong watch face size')
    out=[]
    for n in range(180):
        at=24+n*24
        if at+24>len(b):break
        typ,h,ptr,w,x,y,unk,frames,unk2,other=struct.unpack_from('<HHIHHHHHHI',b,at)
        if typ==0 or ptr==0:break
        if w<1 or h<1 or frames<1 or ptr+w*h*2*frames>len(b):raise ValueError('Out of bounds record '+str(n))
        out.append(dict(id=typ,w=w,h=h,x=x,y=y,ptr=ptr,frames=frames,table_offset=at))
    ids={r['id'] for r in out}
    if len(out)<20 or not {10,17}.issubset(ids):raise ValueError('Unexpected type IDs')
    if any(r['w']!=W or r['h']!=H or r['frames']!=1 for r in out if r['id'] in (10,17)):
        raise ValueError('Image size contract invalid')
    return out

def art_background(reference):
    original=Image.open(reference).convert('RGB').resize((W,H),Image.Resampling.LANCZOS)
    clean=Image.new('RGB',(W,H),(0,3,11))
    a=clean.load();old=original.load()
    for y in range(H):
        for x in range(W):
            r=math.hypot(x-119.5,y-119.5)
            # Preserve chosen concept's holographic edge and neon accents.
            if r>=99:
                k=0.92 if r<117 else 0.75
            else:k=0.0
            b=old[x,y]
            a[x,y]=tuple(min(255,int(a[x,y][i]*(1-k)+b[i]*k)) for i in range(3))
    # Preserve small holographic walking silhouette from the chosen art,
    # while excluding the original example health/time/weather numbers.
    src=original.convert('RGBA')
    mm=Image.new('L',(240,240),0)
    md=ImageDraw.Draw(mm)
    md.ellipse((105,143,140,190),fill=220)
    mm=mm.filter(ImageFilter.GaussianBlur(2.3))
    clean.paste(src,mask=mm)
    d=ImageDraw.Draw(clean)
    cyan=(0,212,245);green=(107,243,41)
    # Geometric contours matching chosen blue-green HUD; no static health numbers.
    d.rounded_rectangle((71,83,190,120),radius=8,fill=(1,10,21),outline=cyan,width=1)
    d.line((75,86,185,86),fill=(4,75,98),width=1)
    d.text((88,73),'TIME',font=font(8),fill=(105,230,255))
    d.ellipse((111,29,167,85),fill=(1,11,21),outline=green,width=1)
    d.arc((114,32,164,82),-45,210,fill=cyan,width=1)
    d.text((115,22),'BATT',font=font(7),fill=(160,255,112))
    d.rounded_rectangle((14,119,72,146),radius=5,fill=(1,11,23),outline=cyan,width=1)
    d.rounded_rectangle((139,129,223,166),radius=5,fill=(1,11,23),outline=green,width=1)
    d.rounded_rectangle((22,170,99,205),radius=5,fill=(1,11,23),outline=cyan,width=1)
    d.rounded_rectangle((144,170,213,205),radius=5,fill=(1,11,23),outline=green,width=1)
    d.rounded_rectangle((76,204,167,223),radius=6,fill=(0,9,19),outline=cyan,width=1)
    # Holographic human silhouette: small central ornamental mark only.
    d.ellipse((115,155,123,163),outline=cyan,width=1)
    d.line((119,164,116,177,111,184),fill=cyan,width=2)
    d.line((117,169,128,173,135,166),fill=cyan,width=2)
    d.line((116,177,106,194),fill=cyan,width=2)
    d.line((116,177,127,192),fill=cyan,width=2)
    d.ellipse((100,186,137,198),outline=green,width=1)
    d.arc((93,181,142,204),0,178,fill=cyan,width=1)
    return clean

def encode565(img):
    data=bytearray(W*H*2)
    img=img.convert('RGB')
    for j,(r,g,b) in enumerate(img.getdata()):
        val=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        data[2*j]=(val>>8)&255;data[2*j+1]=val&255
    return bytes(data)

def decode565(blob,w,h,column_major=False):
    vals=struct.unpack('>'+str(w*h)+'H',blob)
    # 240x240 backgrounds: row-major; multi-frame indicator sprites: column-major.
    # This distinction was verified by reconstruction of original digit 0-9,
    # weekday/month sprites and weather icon families from the supplied BIN.
    if column_major:
        vals=[vals[x*h+y] for y in range(h) for x in range(w)]
    im=Image.new('RGB',(w,h))
    im.putdata([((v>>11&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31) for v in vals]);return im

def simulation(b,records,background):
    result=background.convert('RGB')
    # Simulated frame assembly; black pixels of numeric sprites treated transparent.
    for r in records:
        if r['id'] in (10,17):continue
        w,h,x,y=r['w'],r['h'],r['x'],r['y']
        if x+w>240 or y+h>240:continue
        # Frame indexes in 14-frame decimal family: 3=0 ... 12=9.
        # Other types use a representative valid frame; preview is an example.
        demo_frames={4:5,5:11,6:3,8:3,12:12,13:7,15:13,16:2,
                     19:10,20:14,21:7,22:1,25:6,30:9,31:0,33:8,34:0,
                     47:9,48:0,49:0}
        frame_index=min(r['frames']-1,demo_frames.get(r['id'],0))
        off=r['ptr']+(w*h*2*frame_index)
        im=decode565(b[off:off+w*h*2],w,h,column_major=True).convert('RGBA')
        pix=list(im.getdata());im.putdata([(p[0],p[1],p[2],0 if max(p[:3])<16 else 255) for p in pix])
        result.paste(im,(x,y),im)
    return result

def build(src,ref,out):
    out.mkdir(parents=True,exist_ok=True)
    b=Path(src).read_bytes();records=parse(b)
    prepared=art_background(ref);data=encode565(prepared)
    candidate=bytearray(b)
    display_record=next(r for r in records if r['id']==17)
    preview_record=next(r for r in records if r['id']==10)
    assert len(data)==240*240*2
    candidate[display_record['ptr']:display_record['ptr']+len(data)]=data
    # Render the real existing sprites over the rebuilt background.
    # This is an OFFLINE compositing simulation, not a device screenshot.
    simulated=simulation(b,records,prepared)
    preview_bytes=encode565(simulated)
    candidate[preview_record['ptr']:preview_record['ptr']+len(preview_bytes)]=preview_bytes
    newcrc=zlib.crc32(candidate[24:])&0xffffffff
    struct.pack_into('<I',candidate,8,newcrc)
    generated=out/'D1898001_HOLO_V2_OFFLINE_UNTESTED.bin'
    generated.write_bytes(candidate)
    parsed=parse(candidate)
    assert parsed==records
    modified=[(i,len(b)) for i in range(len(b)) if candidate[i]!=b[i]]
    permitted={8,9,10,11}
    permitted.update(range(display_record['ptr'],display_record['ptr']+len(data)))
    permitted.update(range(preview_record['ptr'],preview_record['ptr']+len(preview_bytes)))
    assert all(i in permitted for i,_ in modified),'Unexpected modification outside allowed ranges'
    assert b[:8]==candidate[:8] and b[12:preview_record['ptr']]==candidate[12:preview_record['ptr']]
    for r in records:
        if r['id'] in(10,17):continue
        size=r['w']*r['h']*r['frames']*2
        assert b[r['ptr']:r['ptr']+size]==candidate[r['ptr']:r['ptr']+size]
    prepared.save(out/'HOLO_V2_live_background.png')
    simulated.save(out/'HOLO_V2_preview_SIMULATION.png')
    manifest={
       'target_firmware_claim':'RB235DCEV004137 (unverified .bin mapping)',
       'source_sha256':hashlib.sha256(b).hexdigest(),
       'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
       'bytes':len(candidate),'image_data_modified_ids':[10,17],
       'record_table_preserved':True,'other_20_assets_unchanged':True,
       'sprite_order_verified':'column-major for small element frames; full-frame images row-major',
       'original_record_count':len(records),
       'unchanged_file_id':struct.unpack_from('<I',b,0)[0],
       'unchanged_payload_length':struct.unpack_from('<I',b,4)[0],
       'crc32_new':f'{newcrc:08X}',
       'crc32_verified':(zlib.crc32(candidate[24:])&0xffffffff)==newcrc,
       'modified_byte_count':len(modified),
       'warning':'NOT TESTED on watch, no flash, not a firmware update. Needs actual sync compatibility check.'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(manifest,indent=2))
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True)
    p.add_argument('--holo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.original,a.holo,a.out)
