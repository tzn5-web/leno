#!/usr/bin/env python3
"""Build reversible GloryFit 240x240 HOLO candidate from owner's own dial templates.

NO ADB, NO BLE, NO device writes. A design proof, not a tested install path.
Input ZIPs must be supplied by watch owner; proprietary binaries are not included in source.
"""
from __future__ import annotations
import argparse, io, json, math, re, struct, zipfile, zlib, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE='assets/DialCustom/dial_1_circle_240x240/'
ORIG='dial_10027_circle_240x240/'
CYAN=(0,219,255); GREEN=(135,255,26); WHITE=(228,253,255)
FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/clear-sans/ClearSans-Bold.ttf',
    'C:/Windows/Fonts/arialbd.ttf',
    'C:/Windows/Fonts/segoeuib.ttf',
]

def font(sz,bold=True):
    for path in FONT_CANDIDATES:
        try: return ImageFont.truetype(path, sz)
        except OSError: pass
    return ImageFont.load_default()

def canvas(rgb=False,size=(240,240)):
    return Image.new('RGB' if rgb else 'RGBA', size, (0,0,0) if rgb else (0,0,0,0))
def mask_hole(im,box,radius=8,outline=CYAN):
    d=ImageDraw.Draw(im,'RGBA')
    x1,y1,x2,y2=box
    d.rounded_rectangle(box,radius,fill=(0,3,10,252),outline=(*outline,190),width=1)
    d.line((x1+9,y1+2,x2-11,y1+2),fill=(*outline,55),width=1)
def text_fit(d,xy,what,sz,color=WHITE):
    d.text(xy,what,font=font(sz),fill=color,stroke_width=0)
def bg_from_reference(src):
    # Uses the exact selected HOLO artwork for rings, ECG and central hologram.
    im=Image.open(src).convert('RGB').resize((240,240),Image.Resampling.LANCZOS).convert('RGBA')
    # Remove all static measurements in the artwork; the real readings are transparent sprites.
    # This is *not* an attempt to fake heart rate / weather / oxygen readings.
    for b in [(57,31,186,52),(37,54,204,99),(86,15,161,34),(99,118,143,145),
              (147,142,218,179),(47,147,95,177),(92,198,185,226)]:
        mask_hole(im,b,8,CYAN if b[0]<90 else GREEN)
    d=ImageDraw.Draw(im,'RGBA')
    text_fit(d,(104,124),'HR',13,GREEN)
    text_fit(d,(55,152),'O₂',11,CYAN)
    text_fit(d,(112,209),'METEO',9,CYAN)
    text_fit(d,(173,175),'PAȘI',7,CYAN)
    d.text((72,36),'HOLO',font=font(9),fill=CYAN)
    d.text((149,36),'SMART',font=font(9),fill=GREEN)
    d.text((91,20),'BAT',font=font(8),fill=WHITE)
    return im.convert('RGB')

def glyph(ch,w,h,color,stroke=False):
    im=canvas(size=(w,h))
    if not ch:return im
    d=ImageDraw.Draw(im)
    # Fit measured text bounds into exact original glyph dimensions.
    size=int(h*0.92)
    ft=font(size)
    while size>5:
        bb=d.textbbox((0,0),ch,font=ft)
        if bb[2]-bb[0] <= w-1 and bb[3]-bb[1] <= h-2:break
        size-=1;ft=font(size)
    bb=d.textbbox((0,0),ch,font=ft)
    xx=(w-(bb[2]-bb[0]))//2-bb[0];yy=(h-(bb[3]-bb[1]))//2-bb[1]
    d.text((xx,yy),ch,font=ft,fill=(*color,255))
    return im

def symbols(src_zip, prefix):
    names={}
    with zipfile.ZipFile(src_zip) as z:
        for x in z.infolist():
            if x.filename.startswith(prefix) and not x.is_dir():names[x.filename]=z.read(x)
    assert names, 'No dial at expected root '+prefix
    return names

def edit_config(items,prefix,layer,w,h,x,y,suffix=''):
    for name in list(items):
        if name.startswith(prefix+layer+'/config_'):
            del items[name]
    name=f'{prefix}{layer}/config_{w}x{h}_{x}x{y}{suffix}.txt'
    items[name]=b''

def valid_original_items(items):
    original={}
    for n,raw in items.items():
        if n.endswith('.png'):
            im=Image.open(io.BytesIO(raw));original[n]=im.size
    return original

def save_image(items,prefix,layer,filename,img,origsize):
    name=prefix+layer+'/'+filename
    assert name in items,f'missing supported asset {name}'
    assert img.size==origsize[name],(name,img.size,origsize[name])
    buf=io.BytesIO();img.save(buf,format='PNG',optimize=True);items[name]=buf.getvalue()

def build(stock_zip,source,out_dir):
    prefix=BASE
    items=symbols(stock_zip,prefix)
    original_names=set(items); original_size=valid_original_items(items)
    background=bg_from_reference(source)
    save_image(items,prefix,'background','1.png',background,original_size)
    # Status elements retained from validated circular stock template.
    locations={
      'timehour1':(38,55),'timehour2':(70,55),
      'hour2min':(102,55),'timemin1':(134,55),'timemin2':(166,55),
      'stepnum1':(167,151),'stepnum2':(176,151),'stepnum3':(185,151),
      'stepnum4':(194,151),'stepnum5':(203,151),
      'timemonth1':(78,106),'timemonth2':(87,106),
      'day2month':(96,106),'timeday1':(105,106),'timeday2':(114,106),
      'week':(134,105),'battery':(126,19),'iconbluetooth':(155,19),
      'iconstep':(150,150),'stepproccess':(130,184),'ampm':(188,109),
    }
    for layer,(x,y) in locations.items():
        for n,dims in original_size.items():
            if n.startswith(prefix+layer+'/'):
                w,h=dims
                edit_config(items,prefix,layer,w,h,x,y,'_2' if layer.startswith('timemonth') else '')
                break
    symbol_indices={0:'−',1:'.',2:'/',13:':'}
    for layer,color in [('timehour1',CYAN),('timehour2',CYAN),('timemin1',GREEN),('timemin2',GREEN),
                        ('stepnum1',GREEN),('stepnum2',GREEN),('stepnum3',GREEN),('stepnum4',GREEN),
                        ('stepnum5',GREEN),('timemonth1',CYAN),('timemonth2',CYAN),
                        ('timeday1',CYAN),('timeday2',CYAN)]:
        for i in range(14):
            ch=symbol_indices.get(i,str(i-3) if 3<=i<=12 else '')
            fn=f'{i:02}.png';full=prefix+layer+'/'+fn
            w,h=original_size[full];glyph_im=glyph(ch,w,h,color)
            save_image(items,prefix,layer,fn,glyph_im,original_size)
    # Battery has 5 states exactly as factory; no new unsupported layer.
    for i in range(5):
        fn=f'{i}.png';full=prefix+'battery/'+fn
        w,h=original_size[full];im=canvas(size=(w,h));d=ImageDraw.Draw(im)
        d.rounded_rectangle((0,1,w-3,h-2),radius=2,outline=CYAN,width=1)
        d.rectangle((w-2,3,w-1,h-4),fill=CYAN)
        fill=max(1,round((w-6)*(i+1)/5));d.rectangle((2,3,2+fill,h-4),fill=GREEN)
        save_image(items,prefix,'battery',fn,im,original_size)
    # Clock colon occupies same 32x45 supported graphic rectangle.
    w,h=original_size[prefix+'hour2min/1.png']
    save_image(items,prefix,'hour2min','1.png',glyph(':',w,h,CYAN),original_size)
    # Step icon only decorative in its own original 13x15 layer.
    w,h=original_size[prefix+'iconstep/1.png']
    im=canvas(size=(w,h));d=ImageDraw.Draw(im);d.ellipse((2,0,7,5),fill=GREEN)
    d.line((6,6,7,11,11,14),fill=GREEN,width=2);d.line((7,10,2,13),fill=GREEN,width=2)
    save_image(items,prefix,'iconstep','1.png',im,original_size)
    # A gradient progress-bar family with all 11 supported frames.
    for i in range(11):
        fn=f'{i}.png';full=prefix+'stepproccess/'+fn
        w,h=original_size[full];im=canvas(size=(w,h));d=ImageDraw.Draw(im)
        d.rounded_rectangle((0,0,w-1,h-1),radius=2,fill=(8,45,54,255))
        progress=round(i*w/10)
        if progress:d.rectangle((0,0,progress-1,h-1),fill=(*GREEN,255))
        save_image(items,prefix,'stepproccess',fn,im,original_size)
    # Keep week, ampm, BT original frame count, but tint original colored whites to cyan.
    # Preview is generated as a *simulation*, not proof of device output.
    preview=background.convert('RGBA')
    def layer(layer,filename):
        for n,raw in items.items():
            if n==prefix+layer+'/'+filename:
                cfg=[v for v in items if v.startswith(prefix+layer+'/config_')]
                m=re.search(r'config_(\d+)x(\d+)_(\d+)x(\d+)',cfg[0])
                pt=(int(m[3]),int(m[4]))
                im=Image.open(io.BytesIO(raw)).convert('RGBA')
                preview.alpha_composite(im,pt)
                return
        raise KeyError((layer,filename))
    for lay,ch in [('timehour1','1'),('timehour2','4'),('timemin1','2'),('timemin2','6')]:
        layer(lay,f'{int(ch)+3:02}.png')
    layer('hour2min','1.png')
    for lay,ch in [('stepnum1','0'),('stepnum2','7'),('stepnum3','3'),('stepnum4','4'),('stepnum5','5')]:
        layer(lay,f'{int(ch)+3:02}.png')
    layer('battery','3.png')
    layer('stepproccess','7.png');layer('iconstep','1.png')
    for lay,ch in [('timemonth1','1'),('timemonth2','1'),('timeday1','0'),('timeday2','9')]:layer(lay,f'{int(ch)+3:02}.png')
    save_image(items,prefix,'preview','1.png',preview.convert('RGB'),original_size)
    save_image(items,prefix,'preview','preview_bg.png',background,original_size)
    assert len(items)==len(original_names), 'Asset count changed'
    assert {n for n in items if '/config_' not in n}=={n for n in original_names if '/config_' not in n}, 'Nonconfig path changed'
    assert valid_original_items(items)==original_size, 'Image-size contract mismatch'
    out=out_dir/'Watch6T_HOLO_dynamic_STOCK_TEMPLATE_UNTESTED.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(items.items()):z.writestr(name,data)
    # Deployed downloaded dials are packaged with the dial directory at ZIP root.
    # Provide this alternate layout for comparison with the original DialCustom ZIP.
    rootzip=out_dir/'Watch6T_HOLO_dynamic_DIALROOT_UNTESTED.zip'
    with zipfile.ZipFile(rootzip,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(items.items()):
            z.writestr(name.replace(BASE,'dial_1_circle_240x240/',1),data)
    preview.save(out_dir/'HOLO_preview_dynamic_SIMULATION.png')
    background.save(out_dir/'HOLO_base_240.png')
    meta={'format':'GloryFit template ZIP - candidate','source_template':str(stock_zip.name),
          'asset_count':len(items),'all_original_nonconfig_paths_preserved':True,
          'all_original_png_dimensions_preserved':True,
          'supported_dynamic_layers':['time','date','weekday','steps','step_progress','battery'],
          'NOT_VERIFIED':['install compatibility','heart rate','SpO2','weather','BLE upload route'],
          'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
          'dialroot_sha256':hashlib.sha256(rootzip.read_bytes()).hexdigest()}
    (out_dir/'validation.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta

def main():
    a=argparse.ArgumentParser();a.add_argument('--stock',type=Path,required=True);a.add_argument('--holo',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    o=a.parse_args();o.out.mkdir(parents=True,exist_ok=True)
    print(json.dumps(build(o.stock,o.holo,o.out),indent=2))
if __name__=='__main__': main()
