#!/usr/bin/env python3
"""Emulator-only package alias for the ORIGINAL Xiaomi Glass APK.

Changes package ID and provider identifiers, but never the original DEX,
keycaps, dictionaries, or ARM64 JNI bytes. UNSIGNED and NOT for Samsung.
"""
import argparse
import copy
import struct
import zipfile
from pathlib import Path

ORIGINAL = "com.android.inputmethod.latin"
ALIAS = "com.android.inputmethod.s24qa"
assert len(ORIGINAL) == len(ALIAS)
u16 = lambda b,p: struct.unpack_from("<H",b,p)[0]
u32 = lambda b,p: struct.unpack_from("<I",b,p)[0]

def entries(blob):
    if u16(blob,0)!=3 or u16(blob,8)!=1:
        raise ValueError("Expected compiled Android XML")
    p=8
    head,count,flags,start=u16(blob,p+2),u32(blob,p+8),u32(blob,p+16),u32(blob,p+20)
    out=[]
    for idx in range(count):
        pos=p+start+u32(blob,p+head+4*idx)
        if flags & 0x100:
            size=blob[pos];pos+=1
            if size & 128:size=((size&127)<<8)|blob[pos];pos+=1
            size=blob[pos];pos+=1
            if size & 128:size=((size&127)<<8)|blob[pos];pos+=1
            out.append((blob[pos:pos+size].decode("utf8"),pos,size,"utf8"))
        else:
            size=u16(blob,pos);pos+=2
            if size & 32768:size=((size&32767)<<16)|u16(blob,pos);pos+=2
            out.append((blob[pos:pos+size*2].decode("utf-16le"),pos,size*2,"utf-16le"))
    return out

def elements(blob):
    names=[x[0] for x in entries(blob)]
    pos=8+u32(blob,12)
    while pos<len(blob):
        typ,length=u16(blob,pos),u32(blob,pos+4)
        if length<8 or pos+length>len(blob):raise ValueError("Bad binary XML")
        if typ==0x102:
            tag=names[u32(blob,pos+20)]
            begin,stride,count=u16(blob,pos+24),u16(blob,pos+26),u16(blob,pos+28)
            attrs={}
            for i in range(count):
                at=pos+16+begin+stride*i
                key=names[u32(blob,at+4)]
                raw=u32(blob,at+8)
                attrs[key]=(names[raw] if raw!=0xffffffff else
                           names[u32(blob,at+16)] if blob[at+15]==3 else
                           u32(blob,at+16))
            yield tag,attrs
        pos+=length

def manifest_with_alias(manifest):
    data=bytearray(manifest)
    substitutions={
        ORIGINAL:ALIAS,
        ORIGINAL+".androidx-startup":ALIAS+".androidx-startup",
        ORIGINAL+".HIDE_SOFT_INPUT":ALIAS+".HIDE_SOFT_INPUT",
        ORIGINAL+".DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION":
            ALIAS+".DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION",
    }
    counts={s:0 for s in substitutions}
    for value,pos,size,encoding in entries(data):
        if value in substitutions:
            new=substitutions[value].encode(encoding)
            if len(new)!=size:raise ValueError("Alias changes AXML size")
            data[pos:pos+size]=new
            counts[value]+=1
    if counts[ORIGINAL]!=1 or counts[ORIGINAL+".androidx-startup"]!=1:
        raise ValueError("Unexpected package/startup authority string pool")
    if any(x>1 for x in counts.values()):raise ValueError("Ambiguous pool entries")
    parsed=list(elements(bytes(data)))
    roots=[a for tag,a in parsed if tag=="manifest"]
    services=[a for tag,a in parsed if tag=="service"
              and a.get("permission")=="android.permission.BIND_INPUT_METHOD"]
    providers=[a for tag,a in parsed if tag=="provider"]
    if len(roots)!=1 or roots[0].get("package")!=ALIAS:
        raise ValueError("Package ID not changed")
    if len(services)!=1 or services[0].get("name")!=ORIGINAL+".LatinIME":
        raise ValueError("Original Java IME service was altered")
    if not any(a.get("authorities")==ALIAS+".androidx-startup" for a in providers):
        raise ValueError("Startup authority still conflicts with AOSP")
    return bytes(data)

def resources_with_alias(resource_table):
    data=resource_table
    for encoding in ("utf8","utf-16le"):
        old=ORIGINAL.encode(encoding)
        if data.count(old)!=1:
            raise ValueError("Expected exactly one "+encoding+" package/authority resource")
        data=data.replace(old,ALIAS.encode(encoding),1)
    if len(data)!=len(resource_table):raise ValueError("ResTable size changed")
    return data

def build(original_path,output_path):
    if original_path.resolve()==output_path.resolve() or output_path.exists():
        raise ValueError("Refusing to overwrite any APK")
    with zipfile.ZipFile(original_path) as src,zipfile.ZipFile(output_path,"w",allowZip64=True) as dst:
        updated_manifest=manifest_with_alias(src.read("AndroidManifest.xml"))
        updated_resources=resources_with_alias(src.read("resources.arsc"))
        for item in src.infolist():
            name=item.filename
            if name.startswith("META-INF/") and name.upper().endswith((".RSA",".SF",".MF",".DSA",".EC")):
                continue
            payload=(updated_manifest if name=="AndroidManifest.xml" else
                     updated_resources if name=="resources.arsc" else src.read(name))
            dst.writestr(copy.copy(item),payload)
    with zipfile.ZipFile(original_path) as a,zipfile.ZipFile(output_path) as b:
        assert b.testzip() is None
        changed={n for n in a.namelist() if n in b.namelist() and a.read(n)!=b.read(n)}
        assert changed=={"AndroidManifest.xml","resources.arsc"},changed
        for n in a.namelist():
            if n in ("classes.dex","classes2.dex") or n.startswith(("res/","assets/","lib/")):
                assert a.read(n)==b.read(n),n
    print("PASS: test-only alias; original DEX, key visuals and ARM64 JNI unchanged")
    print("PASS: manifest and resource-table package IDs / provider authorities isolated")
    print("UNSIGNED PRIVATE EMULATOR TEST APK (NEVER INSTALL ON S24):",output_path)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original_unsigned_apk",type=Path)
    p.add_argument("test_only_alias_unsigned_apk",type=Path)
    a=p.parse_args()
    build(a.original_unsigned_apk,a.test_only_alias_unsigned_apk)
