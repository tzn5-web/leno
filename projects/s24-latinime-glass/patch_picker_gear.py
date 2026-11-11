#!/usr/bin/env python3
"""Redirect IME settings gear to GlassActivity and hide launcher icon.
The supplied original/glass APK is user's own input; output remains unsigned.
DEX, original keyboard keycaps, images and language resources are untouched.
"""
import argparse
import copy
import struct
import zipfile
from pathlib import Path

OLD = "com.android.inputmethod.latin.settings.SettingsActivity"
NEW = "com.android.inputmethod.latin.setup.GlassActivity"
LAUNCHER = "android.intent.category.LAUNCHER"


def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def put32(b, o, n): struct.pack_into("<I", b, o, n)

def pool(b):
    assert u16(b, 0) == 3 and u16(b, 8) == 1
    head, size = u16(b, 10), u32(b, 12)
    count, styles, flags, start, _ = struct.unpack_from("<IIIII", b, 16)
    assert not styles
    strings = []
    for i in range(count):
        p = 8 + start + u32(b, 8 + head + 4*i)
        if flags & 256:
            def length8(p):
                n = b[p]; p += 1
                if n & 128: n, p = ((n & 127) << 8) | b[p], p+1
                return n, p
            _, p = length8(p)
            n, p = length8(p)
            strings.append(b[p:p+n].decode("utf-8"))
        else:
            def length16(p):
                n = u16(b, p); p += 2
                if n & 32768: n, p = ((n & 32767) << 16) | u16(b, p), p+2
                return n, p
            n, p = length16(p)
            strings.append(b[p:p+n*2].decode("utf-16le"))
    return strings, head, size, flags

def len8(n):
    return bytes([n]) if n < 128 else bytes([128 | (n >> 8), n & 255])
def len16(n):
    return struct.pack("<H",n) if n < 32768 else struct.pack("<HH",32768 | (n >> 16),n & 65535)

def update_ime_settings(b):
    strings, head, size, flags = pool(b)
    assert strings.count(OLD) == 1
    strings[strings.index(OLD)] = NEW
    data, offsets = bytearray(), []
    for s in strings:
        offsets.append(len(data))
        if flags & 256:
            v = s.encode("utf-8")
            data += len8(len(s.encode("utf-16le"))//2) + len8(len(v)) + v + b"\x00"
        else:
            v = s.encode("utf-16le")
            data += len16(len(v)//2) + v + b"\x00\x00"
    while len(data) % 4: data.append(0)
    outpool = bytearray(b[8:8+head])
    start = head + 4*len(strings)
    put32(outpool,4,start+len(data))
    put32(outpool,20,start)
    outpool += b"".join(struct.pack("<I",v) for v in offsets) + data
    out = bytearray(b[:8] + outpool + b[8+size:])
    put32(out,4,len(out))
    assert NEW in pool(out)[0]
    return bytes(out)

def attr(b, offset, names, key):
    start, stride, count = u16(b,offset+24),u16(b,offset+26),u16(b,offset+28)
    for i in range(count):
        at = offset + 16 + start + stride*i
        if names[u32(b,at+4)] == key:
            raw = u32(b,at+8)
            if raw != 0xffffffff: return names[raw]
            if b[at+15] == 3: return names[u32(b,at+16)]
    return None

def hide_icon(b):
    names, _, poolsize, _ = pool(b)
    offset = 8 + poolsize
    chunks = []
    skipping = False
    removed = 0
    while offset < len(b):
        typ, _, n = struct.unpack_from("<HHI",b,offset)
        assert 8 <= n <= len(b)-offset
        name = names[u32(b,offset+20)] if typ in (0x102,0x103) else None
        if typ==0x102 and name=="category" and attr(b,offset,names,"name")==LAUNCHER:
            assert not skipping
            skipping=True
            removed+=1
        elif typ==0x103 and name=="category" and skipping:
            skipping=False
        else:
            chunks.append(b[offset:offset+n])
        offset+=n
    assert removed==1 and not skipping, "Expected one launcher intent category"
    out=bytearray(b[:8+poolsize]+b"".join(chunks))
    put32(out,4,len(out))
    return bytes(out)

def main(source, destination):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(destination,"w") as dst:
        im=update_ime_settings(src.read("res/xml/method.xml"))
        manifest=src.read("AndroidManifest.xml")
        assert NEW in pool(manifest)[0]
        manifest=hide_icon(manifest)
        for item in src.infolist():
            name=item.filename
            if name.startswith("META-INF/") and name.upper().endswith((".RSA",".SF",".MF",".DSA",".EC")):continue
            data=im if name=="res/xml/method.xml" else manifest if name=="AndroidManifest.xml" else src.read(name)
            dst.writestr(copy.copy(item),data)
    with zipfile.ZipFile(source) as a, zipfile.ZipFile(destination) as b:
        altered = [n for n in a.namelist() if n in b.namelist() and a.read(n)!=b.read(n)]
        assert sorted(altered)==["AndroidManifest.xml","res/xml/method.xml"]
        for n in ("classes.dex","classes2.dex"):
            assert a.read(n)==b.read(n),n
        assert NEW in pool(b.read("res/xml/method.xml"))[0]
    print("PASS: IME gear points to GlassActivity; launcher icon hidden; keys and resources untouched.")
    print("Unsigned APK:", destination)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original",type=Path)
    p.add_argument("unsigned",type=Path)
    x=p.parse_args()
    main(x.original,x.unsigned)
