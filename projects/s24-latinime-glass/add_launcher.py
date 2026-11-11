#!/usr/bin/env python3
"""Add a launcher entry to the existing GlassActivity using binary Android XML.
Does not modify the original keycaps, layouts, or Java bytecode.
"""
import struct
U16=lambda b,o:struct.unpack_from('<H',b,o)[0]
U32=lambda b,o:struct.unpack_from('<I',b,o)[0]
W16=lambda n:struct.pack('<H',n)
W32=lambda n:struct.pack('<I',n)
SENT=0xffffffff

def strings(b):
    p=8; count=U32(b,p+8); flags=U32(b,p+16); start=U32(b,p+20); h=U16(b,p+2)
    assert flags==0
    out=[]
    for i in range(count):
        off=p+start+U32(b,p+h+i*4)
        length=U16(b,off);off+=2
        if length&32768:
            length=((length&32767)<<16)|U16(b,off);off+=2
        out.append(b[off:off+length*2].decode('utf-16le'))
    return out

def add_strings(b,added):
    p=8; head=U16(b,p+2); size=U32(b,p+4)
    count=U32(b,p+8);start=U32(b,p+20)
    assert head==28 and U32(b,p+12)==0 and start==head+count*4
    h=bytearray(b[p:p+head]);offs=b[p+head:p+head+count*4]
    payload=bytearray(b[p+start:p+size]);offsets=[]
    for s in added:
        offsets.append(len(payload))
        payload+=W16(len(s))+s.encode('utf-16le')+W16(0)
    while len(payload)%4:payload+=b'\0'
    struct.pack_into('<I',h,4,head+(count+len(added))*4+len(payload))
    struct.pack_into('<I',h,8,count+len(added))
    struct.pack_into('<I',h,20,start+4*len(added))
    return bytes(h)+offs+b''.join(W32(n) for n in offsets)+payload

def start_category(category_index, name_index, ns_index, value_index):
    n=W16(0x102)+W16(16)+W32(56)+W32(1)+W32(SENT)
    ext=W32(SENT)+W32(category_index)+W16(20)+W16(20)+W16(1)+W16(0)+W16(0)+W16(0)
    attr=W32(ns_index)+W32(name_index)+W32(value_index)+W16(8)+bytes([0,3])+W32(value_index)
    return n+ext+attr

def end_category(category_index):
    return W16(0x103)+W16(16)+W32(24)+W32(1)+W32(SENT)+W32(SENT)+W32(category_index)

def patch(blob):
    b=bytes(blob)
    assert U16(b,0)==3
    names=strings(b)
    if 'android.intent.category.LAUNCHER' in names:
        raise ValueError('Already contains a launcher category')
    assert 'category' not in names
    pool=add_strings(b,['category','android.intent.category.LAUNCHER'])
    cat,launcher=len(names),len(names)+1
    nameidx=names.index('name')
    uriidx=names.index('http://schemas.android.com/apk/res/android')
    output=[];in_activity=False;in_filter=False;main=False;added=False
    offset=8+U32(b,12)
    while offset<len(b):
        typ,_,size=struct.unpack_from('<HHI',b,offset)
        assert 8<=size<=len(b)-offset
        chunk=b[offset:offset+size]
        if typ==0x102:
            tag=names[U32(b,offset+20)]
            if tag=='activity':
                in_activity=False
                begin=U16(b,offset+24);step=U16(b,offset+26);count=U16(b,offset+28)
                for i in range(count):
                    attr=offset+16+begin+i*step
                    if names[U32(b,attr+4)]=='name':
                        raw=U32(b,attr+8)
                        ref=raw if raw!=SENT else U32(b,attr+16)
                        in_activity=names[ref]=='com.android.inputmethod.latin.setup.GlassActivity'
            elif tag=='intent-filter' and in_activity:
                in_filter=True;main=False
            elif tag=='action' and in_filter:
                begin=U16(b,offset+24);step=U16(b,offset+26);count=U16(b,offset+28)
                for i in range(count):
                    attr=offset+16+begin+i*step
                    if names[U32(b,attr+4)]=='name':
                        raw=U32(b,attr+8)
                        ref=raw if raw!=SENT else U32(b,attr+16)
                        if names[ref]=='android.intent.action.MAIN':main=True
        elif typ==0x103:
            tag=names[U32(b,offset+20)]
            if tag=='intent-filter' and in_filter:
                if main:
                    output.append(start_category(cat,nameidx,uriidx,launcher))
                    output.append(end_category(cat))
                    added=True
                in_filter=False;main=False
            if tag=='activity':in_activity=False
        output.append(chunk);offset+=size
    if not added:raise ValueError('No MAIN intent filter on GlassActivity')
    result=bytearray(b[:8]+pool+b''.join(output))
    struct.pack_into('<I',result,4,len(result))
    assert 'android.intent.category.LAUNCHER' in strings(result)
    return bytes(result)
