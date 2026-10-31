#!/usr/bin/env python3
"""Inspect a PE32 file statically. No PE code is executed."""
import argparse, hashlib, json, re, struct
from pathlib import Path
TOKENS=["CreateFileA","CreateFileW","ReadFile","ReadFileEx","GetProcAddress",
        "LoadLibraryA","inflate 1.2.3","incorrect header check",
        "MODELS.IDF","TDGRAPH.IDF",".IDF","IDF"]
def inspect(path):
    data=Path(path).read_bytes()
    if data[:2]!=b"MZ":raise ValueError("MZ header absent")
    pe=struct.unpack_from("<I",data,0x3c)[0]
    if data[pe:pe+4]!=b"PE\\x00\\x00".replace(b"\\x00",b"\x00"):
        raise ValueError("PE signature absent")
    coff=pe+4
    machine,n=struct.unpack_from("<HH",data,coff)
    opt=coff+20
    if struct.unpack_from("<H",data,opt)[0]!=0x10b:raise ValueError("PE32 only")
    entry=struct.unpack_from("<I",data,opt+16)[0]
    base=struct.unpack_from("<I",data,opt+28)[0]
    sections=[]
    for i in range(n):
        p=opt+struct.unpack_from("<H",data,coff+16)[0]+i*40
        name=data[p:p+8].split(b"\x00")[0].decode("ascii","replace")
        vsize,rva,rawlen,raw=struct.unpack_from("<IIII",data,p+8)
        sections.append({"name":name,"rva":rva,"virtual_size":vsize,
                         "raw_offset":raw,"raw_size":rawlen})
    def offset(rva):
        for s in sections:
            if s["rva"]<=rva<s["rva"]+s["raw_size"]:
                return s["raw_offset"]+(rva-s["rva"])
        raise ValueError("Unmapped RVA "+hex(rva))
    def asciiz(p):
        end=data.find(b"\x00",p,min(p+500,len(data)))
        if end<0:raise ValueError("Unterminated name")
        return data[p:end].decode("ascii","replace")
    imports=[]
    import_rva=struct.unpack_from("<I",data,opt+104)[0]
    if import_rva:
        table=offset(import_rva)
        for j in range(200):
            oft,timestamp,fwd,name,first=struct.unpack_from("<IIIII",data,table+20*j)
            if not any((oft,timestamp,fwd,name,first)):break
            dll=asciiz(offset(name))
            for k in range(10000):
                thunk=struct.unpack_from("<I",data,offset((oft or first)+4*k))[0]
                if not thunk:break
                symbol=("#"+str(thunk&65535) if thunk&0x80000000
                        else asciiz(offset(thunk)+2))
                imports.append({"dll":dll,"name":symbol})
    strings={}
    for token in TOKENS:
        hits=[]
        for hit in re.finditer(re.escape(token.encode("ascii")),data):
            raw=hit.start()
            section=next((s for s in sections if s["raw_offset"]<=raw<s["raw_offset"]+s["raw_size"]),None)
            rva=section["rva"]+raw-section["raw_offset"] if section else None
            hits.append({"file_offset":raw,"section":section["name"] if section else None,
                         "rva":rva,"virtual_address":base+rva if rva is not None else None})
        strings[token]=hits[:30]
    return {"program_executed":False,"sha256":hashlib.sha256(data).hexdigest(),
            "bytes":len(data),"format":"PE32","machine":hex(machine),
            "entrypoint_rva":hex(entry),"imagebase":hex(base),
            "sections":sections,"import_count":len(imports),"imports":imports,
            "string_occurrences":strings,
            "warning":"Strings and imports do not identify an IDF decoder by themselves"}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("pe",type=Path)
    parser.add_argument("--output",type=Path,default=Path("autodata_pe_static_audit.json"))
    args=parser.parse_args()
    result=inspect(args.pe)
    args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("Static PE analyzed:",result["bytes"],"bytes,",result["import_count"],"imports")
