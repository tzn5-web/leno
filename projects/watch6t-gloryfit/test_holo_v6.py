#!/usr/bin/env python3
"""Offline tests of actual HOLO V6 output; no connection, no watch writes."""
import sys,struct,zlib,hashlib,json,zipfile
from pathlib import Path
from PIL import Image
p=Path(__file__).resolve().parent
m=json.loads((p/'MANIFEST_V6.json').read_text(encoding='utf-8'))
stock=(p/'D1898001_ORIGINAL_DO_NOT_EDIT.bin').read_bytes()
new=(p/'D1898001_HOLO_V6_BETA_UNTESTED.bin').read_bytes()
assert len(stock)==m['input_bytes'] and len(new)==m['output_bytes']
assert hashlib.sha256(stock).hexdigest()==m['source_sha256']
assert hashlib.sha256(new).hexdigest()==m['output_sha256']
for data in (stock,new):
    assert struct.unpack_from('<HH',data,12)==(240,240)
    assert struct.unpack_from('<I',data,4)[0]==len(data)-24
    assert struct.unpack_from('<I',data,8)[0]==zlib.crc32(data[24:])&0xffffffff
assert new[:4]==stock[:4] and new[12:24]==stock[12:24]
orig,rebuild=[],[]
for i in range(22):
    a=stock[24+24*i:48+24*i]; b=new[24+24*i:48+24*i]
    t,w,pos,h,x,y,rsv,count,extra,last=struct.unpack('<HHIHHHHHHI',b)
    assert 1<=w<=240 and 1<=h<=240 and 1<=count<=255,(t,w,h,count)
    assert x+w<=240 and y+h<=240,(t,x,y,w,h)
    assert pos>=24+22*24+2 and pos+w*h*count*2<=len(new)
    assert a[:2]==b[:2],(i,'type changed')
    assert a[14:24]==b[14:24],(i,'flags, frame count or reserved changed')
    assert b[2:4]!=b''
    orig.append(struct.unpack_from('<H',a)[0]);rebuild.append(t)
assert orig==rebuild and len(set(rebuild))==22
assert new[24+22*24:24+22*24+2]==b'\x00\x00'
assert len(new) < 524288,'V6 exceeds conservative 512KiB provisional ceiling'
with Image.open(p/'HOLO_V6_DYNAMIC_PREVIEW_240.png') as img:
    assert img.size==(240,240)
with Image.open(p/'HOLO_V6_LIVE_BACKGROUND_240.png') as img:
    assert img.size==(240,240)
with Image.open(p/'HOLO_REFERENCE_ORIGINAL.png') as img:
    assert img.size[0]>=1000 and img.size[1]>=1000
print('PASS native format: 22 ID types unchanged; frame counts and metadata retained; all offsets in bounds; CRC and SHA verified; 240x240 images; V6<512KiB')
print('NOT TESTED: actual device max face size, BLE upload protocol, live metric mapping, watch acceptance')
