#!/usr/bin/env python3
"""Read-only DEX method signature index for a supplied APK.
No modification, no protected source publishing. Standard library only.
"""
import argparse, zipfile, struct, re, json

def uleb(data, offset):
    result=0; shift=0
    for _ in range(5):
        x=data[offset];offset+=1;result |= (x&0x7f)<<shift
        if x<128:return result,offset
        shift+=7
    raise ValueError('Bad ULEB')

def dex_strings(b):
    cnt, off=struct.unpack_from('<II',b,0x38)
    out=[]
    for i in range(cnt):
        pos=struct.unpack_from('<I',b,off+i*4)[0]
        _,pos=uleb(b,pos)
        end=b.find(b'\0',pos)
        out.append(b[pos:end].decode('utf8','replace'))
    return out

def dex_methods(b):
    ss=dex_strings(b)
    tc,to=struct.unpack_from('<II',b,0x40)
    types=[ss[struct.unpack_from('<I',b,to+4*i)[0]] for i in range(tc)]
    pc,po=struct.unpack_from('<II',b,0x48)
    protos=[]
    for i in range(pc):
        shorty,return_idx,params_off=struct.unpack_from('<III',b,po+12*i)
        params=[]
        if params_off:
            n=struct.unpack_from('<I',b,params_off)[0]
            params=[types[struct.unpack_from('<H',b,params_off+4+2*j)[0]] for j in range(n)]
        protos.append({'return':types[return_idx],'params':params})
    mc,mo=struct.unpack_from('<II',b,0x58)
    result=[]
    for i in range(mc):
        cls,proto,name=struct.unpack_from('<HHI',b,mo+8*i)
        m=ss[name]
        if re.search(r'(?:watchface|dial|upload|apply|transfer|download)',m,re.I):
            result.append({'idx':i,'name':m,'class':types[cls],**protos[proto]})
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('apk');p.add_argument('--output');a=p.parse_args()
    found=[]
    with zipfile.ZipFile(a.apk) as z:
        for n in z.namelist():
            if re.fullmatch(r'classes\d*.dex',n):
                b=z.read(n)
                for f in dex_methods(b):found.append({'dex':n,**f})
    if a.output:
        with open(a.output,'w',encoding='utf8') as f:json.dump(found,f,indent=2,ensure_ascii=False)
    for row in found:
        if re.search('uploadWatchFace|applyWatchFace|setImageWatchFace|downloadImageWatchFace|getWatchFaceParams|createWatchFace',row['name'],re.I):
            print(row['dex'],row['idx'],row['class'],row['name'],row['params'],row['return'])
    print('Matching methods:',len(found))
if __name__=='__main__':main()
