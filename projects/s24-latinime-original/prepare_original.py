#!/usr/bin/env python3
"""Preserve original Xiaomi/AOSP LatinIME UI and classes; make ABI available to Android.
Builds unsigned APK. Re-sign with Android SDK apksigner. This is a compatibility
candidate, not a proof that the app never learns or persists typed text.
"""
import copy
import struct
import sys
import zipfile
from pathlib import Path


def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def put32(b, o, n): struct.pack_into('<I', b, o, n)
def length8(b, o):
    n = b[o]; o += 1
    if n & 128: n, o = ((n & 127) << 8) | b[o], o+1
    return n, o

def length16(b, o):
    n = u16(b, o); o += 2
    if n & 32768: n, o = ((n & 32767) << 16) | u16(b, o), o+2
    return n, o

def manifest_strings(b):
    typ, header, size = struct.unpack_from('<HHI', b, 8)
    if typ != 1: raise ValueError('Invalid AXML string pool')
    count, _, flags, start, _ = struct.unpack_from('<IIIII', b, 16)
    texts = []
    for index in range(count):
        pos = 8 + start + u32(b, 8+header+index*4)
        if flags & 256:
            _, pos = length8(b, pos)
            n, pos = length8(b, pos)
            texts.append(b[pos:pos+n].decode('utf8'))
        else:
            n, pos = length16(b, pos)
            texts.append(b[pos:pos+n*2].decode('utf-16le'))
    return texts, 8+size

def patch_manifest(raw):
    b = bytearray(raw)
    if u16(b, 0) != 3: raise ValueError('Expected binary manifest')
    names, start = manifest_strings(b)
    chunks = []
    skip_end = False
    removed = []
    have_backup = False
    o = start
    while o < len(b):
        typ, _, size = struct.unpack_from('<HHI', b, o)
        if size < 8 or o+size > len(b): raise ValueError('Broken XML')
        chunk = bytearray(b[o:o+size]); skip = False
        if typ == 0x102:
            name = names[u32(b, o+20)]
            if name == 'uses-permission':
                skip = True; skip_end = True
                atr, step, count = struct.unpack_from('<HHH', b, o+24)
                for i in range(count):
                    at = o+16+atr+i*step
                    if names[u32(b, at+4)] == 'name':
                        rawidx = u32(b, at+8)
                        removed.append(names[rawidx if rawidx != 0xffffffff else u32(b, at+16)])
            elif name == 'application':
                atr, step, count = struct.unpack_from('<HHH', b, o+24)
                for i in range(count):
                    at = 16+atr+i*step
                    if names[u32(chunk, at+4)] == 'allowBackup':
                        if chunk[at+15] != 0x12: raise ValueError('allowBackup format changed')
                        put32(chunk, at+16, 0)
                        have_backup = True
        elif typ == 0x103 and skip_end and names[u32(b, o+20)] == 'uses-permission':
            skip = True; skip_end = False
        if not skip: chunks.append(chunk)
        o += size
    if not have_backup: raise ValueError('allowBackup attribute not found')
    result = bytearray(b[:start] + b''.join(chunks))
    put32(result, 4, len(result))
    return bytes(result), removed

def main(src, dst):
    with zipfile.ZipFile(src) as original, zipfile.ZipFile(dst, 'w') as output:
        manifest, removed = patch_manifest(original.read('AndroidManifest.xml'))
        for info in original.infolist():
            name = info.filename
            if name.startswith('META-INF/') and name.endswith(('.RSA','.DSA','.EC','.SF','.MF')):
                continue
            content = manifest if name == 'AndroidManifest.xml' else original.read(name)
            output.writestr(copy.copy(info), content)
        for abi, source in [('arm64-v8a','assets/lib64/libjni_latinimegoogle.so'),('armeabi-v7a','assets/lib/libjni_latinimegoogle.so')]:
            output.writestr(f'lib/{abi}/libjni_latinimegoogle.so', original.read(source), compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(src) as original, zipfile.ZipFile(dst) as repaired:
        assert original.read('classes.dex') == repaired.read('classes.dex')
        assert patch_manifest(repaired.read('AndroidManifest.xml'))[1] == []
    print('Removed requested permissions:', ', '.join(removed))
    print('Preserved classes.dex and resource files; added both native ABIs.')
    print('Unverified: One UI device behavior and whether internal learning/persistence is disabled.')

if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('Usage: prepare_original.py LatinIME.apk unsigned.apk')
    main(Path(sys.argv[1]), Path(sys.argv[2]))
