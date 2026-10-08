#!/usr/bin/env python3
"""Static read-only audit of a purported vanilla YouTube 21.40.5 IPA.
Passing does NOT prove official origin or absence of malware.
"""
import argparse,hashlib,json,plistlib,stat,struct,zipfile
from pathlib import Path,PurePosixPath
SUSPECT=("vanced","revanced","ytkace","substrate","substitute","frida","cycript","tweak","youplus")
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
 return h.hexdigest()
def macho(data):
 if len(data)<32 or data[:4]!=b"\xcf\xfa\xed\xfe" or struct.unpack_from("<I",data,4)[0]!=0x100000c:raise ValueError("not thin arm64 Mach-O")
 n,length=struct.unpack_from("<II",data,16)
 if n<1 or n>4096 or length>len(data)-32:raise ValueError("invalid Mach-O header")
 pos=32;end=32+length;crypt=[];libs=[]
 for _ in range(n):
  if pos+8>end:raise ValueError("truncated command")
  cmd,size=struct.unpack_from("<II",data,pos)
  if size<8 or size%8 or pos+size>end:raise ValueError("invalid load command bounds")
  if cmd in (0x21,0x2c):
   if size<20:raise ValueError("short encryption command")
   crypt.append(struct.unpack_from("<I",data,pos+16)[0])
  if (cmd&0x7fffffff) in (0xc,0xd,0x18,0x1f,0x23) and size>=24:
   off=struct.unpack_from("<I",data,pos+8)[0]
   if 24<=off<size:libs.append(data[pos+off:pos+size].split(b"\0",1)[0].decode("utf8","replace"))
  pos+=size
 if pos!=end:raise ValueError("load command size mismatch")
 return {"cryptids":crypt,"imports":libs}
def audit(path):
 path=Path(path)
 r={"sha256":sha(path),"bytes":path.stat().st_size,"attested_official":False,"guaranteed_malware_free":False}
 with zipfile.ZipFile(path) as z:
  names=set();total=0
  for item in z.infolist():
   p=item.filename
   if not p or p.startswith("/") or "\\" in p or ".." in PurePosixPath(p).parts:raise ValueError("unsafe archive path")
   if p in names:raise ValueError("duplicate ZIP entry")
   names.add(p);total+=item.file_size
   if item.file_size>1536*1024**2 or total>4*1024**3:raise ValueError("oversized archive")
   if stat.S_ISLNK((item.external_attr>>16)&0xffff):raise ValueError("symlink in archive")
  apps={n.split(".app/",1)[0]+".app/" for n in names if n.startswith("Payload/") and ".app/" in n}
  if len(apps)!=1:raise ValueError("not one application")
  root=apps.pop()
  info=plistlib.loads(z.read(root+"Info.plist"))
  if info.get("CFBundleIdentifier")!="com.google.ios.youtube":raise ValueError("wrong bundle")
  if info.get("CFBundleShortVersionString")!="21.40.5":raise ValueError("wrong version")
  exe=info.get("CFBundleExecutable")
  if not isinstance(exe,str) or not exe or "/" in exe or exe.startswith("."):raise ValueError("invalid executable name")
  m=macho(z.read(root+exe))
  flagged=[p for p in names if any(x in p.lower() for x in SUSPECT)]
  flagged+=["IMPORT:"+s for s in m["imports"] if any(x in s.lower() for x in SUSPECT)]
  if z.testzip() is not None:raise ValueError("CRC failure")
  r.update({"entry_count":len(names),"bundle":root,"version":"21.40.5","macho":m,"suspicious_components":sorted(flagged),
   "warning":"Metadata can be spoofed. An unmodified official App Store executable is not proven by this check."})
  r["status"]="REJECT_KNOWN_INJECTION" if flagged else "REJECT_ENCRYPTED" if any(x for x in m["cryptids"]) else "STRUCTURE_PASS_PROVENANCE_UNVERIFIED"
 return r
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("ipa",type=Path);p.add_argument("--out",type=Path);a=p.parse_args()
 try:
  result=audit(a.ipa);exit_code=0 if result["status"]=="STRUCTURE_PASS_PROVENANCE_UNVERIFIED" else 2
 except Exception as error:
  result={"status":"REJECT_INVALID_ARCHIVE","error":str(error)};exit_code=2
 output=json.dumps(result,indent=2,ensure_ascii=False)
 print(output)
 if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(output+"\n")
 raise SystemExit(exit_code)
