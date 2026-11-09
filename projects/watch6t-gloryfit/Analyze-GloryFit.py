#!/usr/bin/env python3
"""Read-only GloryFit bundle inspector. Requires Python 3; no third-party dependencies.
Works with Windows-created ZIP entry paths. Never writes to the watch or phone.
"""
import argparse, collections, hashlib, io, json, re, struct, zipfile, zlib
from pathlib import Path

def inspect_bin(b):
    if len(b)<24: raise ValueError("truncated 24-byte header")
    fid,length,crc=struct.unpack_from("<III",b)
    w,h=struct.unpack_from("<HH",b,12)
    records=[]
    for o in range(24,min(len(b),24+24*160),24):
        if o+24>len(b): break
        typ,ih,pos,iw,x,y,_,frames,_,_=struct.unpack_from("<HHIHHHHHHI",b,o)
        if not typ and not pos: break
        size=iw*ih*2*frames
        records.append({"type":typ,"width":iw,"height":ih,"x":x,"y":y,
                        "frame_count":frames,"pixel_offset":pos,"pixel_bytes":size,
                        "data_in_bounds":pos>=24 and pos+size<=len(b)})
    return {"file_id":fid,"file_bytes":len(b),"resolution":[w,h],
            "payload_size_valid":length==len(b)-24,
            "crc32_valid":crc==(zlib.crc32(b[24:])&0xffffffff),
            "crc32":f"{crc:08x}","records":records}

def parse_bundle(p):
    result={"source":p.name,"size":p.stat().st_size,"apks":[],"faces":[],"packages":[]}
    with zipfile.ZipFile(p) as outer:
        for f in outer.infolist():
            n=f.filename.replace("\\","/")
            if n.startswith("apks/") and n.endswith(".apk"):
                content=outer.read(f)
                a={"filename":Path(n).name,"bytes":len(content),
                   "sha256":hashlib.sha256(content).hexdigest()}
                with zipfile.ZipFile(io.BytesIO(content)) as apk:
                    templ=collections.defaultdict(lambda:collections.Counter())
                    for name in apk.namelist():
                        parts=name.split("/")
                        if len(parts)>4 and parts[:2]==["assets","DialCustom"]:
                            templ[parts[2]][parts[3]]+=1
                    a["dial_templates"]={k:dict(v) for k,v in templ.items()}
                    a["dex_files"]=[x for x in apk.namelist() if re.fullmatch(r"classes\d*.dex",x)]
                result["apks"].append(a)
            elif n.endswith(".bin"):
                b=outer.read(f)
                result["faces"].append({"filename":Path(n).name,
                                        "sha256":hashlib.sha256(b).hexdigest(),
                                        **inspect_bin(b)})
            elif "/DialCustom/" in n and n.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(outer.read(f))) as dial:
                    result["packages"].append({"filename":Path(n).name,"entries":len(dial.namelist()),
                                               "root":dial.namelist()[0]})
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("archive",type=Path)
    parser.add_argument("--output",type=Path,default=Path("watch6t_analysis.json"))
    a=parser.parse_args()
    report=parse_bundle(a.archive)
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    for apk in report["apks"]:
        print(apk["filename"],"templates:",",".join(apk["dial_templates"]) or "none")
    for face in report["faces"]:
        print(face["filename"],"resolution:",face["resolution"],
              "elements:",len(face["records"]),"CRC32:",face["crc32_valid"])
    print("Report:",a.output)

if __name__=="__main__": main()
