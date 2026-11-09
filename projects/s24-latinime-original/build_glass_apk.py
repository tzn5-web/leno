#!/usr/bin/env python3
"""Patch ORIGINAL Xiaomi LatinIME resource/manifest with Glass + emoji DEX.

This tool does NOT create a new keyboard and does NOT overwrite any key graphics.
Use the already-sanitized LatinIME APK from prepare_original.py, the classes2.dex
built by the GitHub Actions Glass addon workflow, then zipalign + apksigner.
"""
import copy
import io
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from PIL import Image

def u16(b,o): return struct.unpack_from('<H',b,o)[0]
def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def p32(b,o,x): struct.pack_into('<I',b,o,x)

def strpool(b):
    sp=8;head=u16(b,sp+2);count=u32(b,sp+8)
    flags=u32(b,sp+16);start=u32(b,sp+20);size=u32(b,sp+4)
    if u32(b,sp+12): raise ValueError('styled AXML not supported')
    strings=[]
    for i in range(count):
        pos=sp+start+u32(b,sp+head+4*i)
        if flags&256:
            n=b[pos];pos+=1
            if n&128:pos+=1
            ln=b[pos];pos+=1
            if ln&128:ln=((ln&127)<<8)|b[pos];pos+=1
            strings.append(b[pos:pos+ln].decode('utf-8'))
        else:
            n=u16(b,pos);pos+=2
            if n&32768:n=((n&32767)<<16)|u16(b,pos);pos+=2
            strings.append(b[pos:pos+n*2].decode('utf-16le'))
    return strings,head,flags,start,size

def appstart(tagidx,nsidx,nameidx,valueidx,exportedidx):
    def attr(name,value,kind):
        if kind=='string':return struct.pack('<IIIHBBI',nsidx,name,value,8,0,3,value)
        return struct.pack('<IIIHBBI',nsidx,name,0xffffffff,8,0,18,0)
    parts=[attr(nameidx,valueidx,'string')]
    if exportedidx is not None:parts.append(attr(exportedidx,0,'false'))
    sz=36+20*len(parts)
    return (struct.pack('<HHIII',0x102,16,sz,0,0xffffffff)
            +struct.pack('<IIHHHHHH',0xffffffff,tagidx,20,20,len(parts),0,0,0)
            +b''.join(parts))

def append_string_pool(original,strings,head,flags,start,size,new):
    count=len(strings)
    offs=[u32(original,8+head+i*4) for i in range(count)]
    raw=bytearray(original[8+start:8+size])
    for string in new:
        offs.append(len(raw))
        utf=string.encode('utf8')
        utf16units=len(string.encode('utf-16le'))//2
        if flags&256:
            assert utf16units<128 and len(utf)<128
            raw.extend(bytes([utf16units,len(utf)])+utf+b'\x00')
        else:
            raw.extend(struct.pack('<H',utf16units)+string.encode('utf-16le')+b'\x00\x00')
    while len(raw)%4:raw.append(0)
    result=bytearray(original[8:8+head])
    p32(result,8,len(offs));p32(result,20,head+4*len(offs))
    result.extend(struct.pack('<'+'I'*len(offs),*offs));result.extend(raw)
    p32(result,4,len(result))
    return bytes(result)

def manifest_patch(b):
    strings,head,flags,start,sz=strpool(b)
    new=['dev.tzn5.glass.GlassLatinIME','dev.tzn5.glass.GlassSettingsActivity']
    ids={s:i for i,s in enumerate(strings)}
    for index,s in enumerate(new): ids[s]=len(strings)+index
    pool=append_string_pool(b,strings,head,flags,start,sz,new)
    out=[];pos=8+sz;updated=added=False
    while pos<len(b):
        typ,h,n=struct.unpack_from('<HHI',b,pos)
        if not n or pos+n>len(b):raise ValueError('broken AXML')
        blob=bytearray(b[pos:pos+n])
        name=strings[u32(blob,20)] if typ in (0x102,0x103) else ''
        if typ==0x102 and name=='service':
            astart,astep,acount=struct.unpack_from('<HHH',blob,24)
            for i in range(acount):
                offset=16+astart+i*astep
                if strings[u32(blob,offset+4)]!='name':continue
                index=u32(blob,offset+8)
                if index==0xffffffff:index=u32(blob,offset+16)
                if strings[index]=='com.android.inputmethod.latin.LatinIME':
                    p32(blob,offset+8,ids[new[0]])
                    p32(blob,offset+16,ids[new[0]])
                    updated=True
        if typ==0x103 and name=='application':
            ns=ids['http://schemas.android.com/apk/res/android'];tag=ids['activity']
            out.append(appstart(tag,ns,ids['name'],ids[new[1]],ids.get('exported')))
            out.append(struct.pack('<HHIIIII',0x103,16,24,0,0xffffffff,0xffffffff,tag))
            added=True
        out.append(blob);pos+=n
    if not (added and updated):raise ValueError('service or application missing')
    data=bytearray(b[:8]+pool+b''.join(out));p32(data,4,len(data))
    return bytes(data)

def transparent_ninepatch(data):
    source=Image.open(io.BytesIO(data)).convert('RGBA')
    source.putalpha(0)
    dest=io.BytesIO();source.save(dest,format='PNG');png=dest.getvalue()
    # Android precompiled nine-patch chunks are essential; do not discard them.
    extras=[];i=8
    while i<len(data):
        length=struct.unpack_from('>I',data,i)[0];tag=data[i+4:i+8]
        if tag in (b'npOl',b'npTc'):
            value=data[i+8:i+8+length]
            extras.append(struct.pack('>I',length)+tag+value+
                          struct.pack('>I',zlib.crc32(tag+value)&0xffffffff))
        i+=12+length
    offset=8+12+struct.unpack_from('>I',png,8)[0]
    return png[:offset]+b''.join(extras)+png[offset:]

def build(original,dex,target):
    with zipfile.ZipFile(original) as old,zipfile.ZipFile(target,'w') as output:
        patched=manifest_patch(old.read('AndroidManifest.xml'))
        for entry in old.infolist():
            name=entry.filename
            if name.startswith('META-INF/') and name.endswith(('.RSA','.DSA','.SF','.MF','.EC')):
                continue
            content=patched if name=='AndroidManifest.xml' else old.read(name)
            if name.startswith('res/') and name.endswith('.9.png') and (
                    'keyboard_background_lxx_' in name or 'keyboard_suggest_strip_lxx_' in name):
                content=transparent_ninepatch(content)
            output.writestr(copy.copy(entry),content)
        addon=Path(dex).read_bytes()
        if not addon.startswith(b'dex\n'):raise ValueError('not DEX')
        output.writestr('classes2.dex',addon,compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(original) as old,zipfile.ZipFile(target) as result:
        assert old.read('classes.dex')==result.read('classes.dex')
        assert all(old.read(n)==result.read(n)
                   for n in old.namelist() if 'btn_keyboard_key_' in n and n.endswith('.png'))
    print('PASS: original LatinIME dex and key images untouched, extra Glass+emoji DEX integrated.')

if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('Usage: build_glass_apk.py sanitized-original.apk classes2.dex unsigned.apk')
    build(*sys.argv[1:4])
