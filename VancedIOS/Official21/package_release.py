#!/usr/bin/env python3
"""Repack a verified YouTube 21.40.5 IPA with independently compiled LOCAL module.
Static verification only. Proprietary decrypted base has unverified provenance.
"""
import argparse,hashlib,json,plistlib,zipfile,subprocess,sys,os,tempfile,shutil,stat
from pathlib import Path,PurePosixPath
VERSION="21.40.5"
BUNDLE="ro.ion.youtubevanced.latest"
SOURCE_HASH="6cfef4ca82720f385b4ab3a7e7171cefb2d95d552d88f15cabe1b559bcf80154"
ROOT="Payload/YouTube.app/"
def hashfile(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for data in iter(lambda:f.read(1024*1024),b""):h.update(data)
 return h.hexdigest()
def check_zip(z):
 names=set()
 for item in z.infolist():
  n=item.filename;p=PurePosixPath(n)
  if not n or p.is_absolute() or ".." in p.parts or "\\" in n:raise ValueError("unsafe zip entry")
  if stat.S_ISLNK(item.external_attr>>16):raise ValueError("symlink in ZIP")
  if n in names:raise ValueError("duplicate ZIP entries")
  names.add(n)
 if z.testzip() is not None:raise ValueError("zip CRC mismatch")
def package(source,intermediate,profile,ytkace_root,out):
 if hashfile(source)!=SOURCE_HASH:raise ValueError("unverified YouTube 21.40.5 source SHA")
 with zipfile.ZipFile(source) as z:
  check_zip(z)
  p=plistlib.loads(z.read(ROOT+"Info.plist"))
  if p["CFBundleIdentifier"]!="com.google.ios.youtube" or p["CFBundleShortVersionString"]!=VERSION:raise ValueError("bad original bundle or version")
 with tempfile.TemporaryDirectory() as td:
  work=Path(td)
  with zipfile.ZipFile(intermediate) as z:
   check_zip(z)
   z.extractall(work)
  app=work/ROOT
  path=app/"Info.plist"
  info=plistlib.loads(path.read_bytes())
  if info.get("CFBundleShortVersionString")!=VERSION:raise ValueError("version changed during injection")
  info["CFBundleIdentifier"]=BUNDLE
  info["CFBundleName"]="YouTube Vanced"
  info["CFBundleDisplayName"]="YouTube Vanced"
  info["CFBundleURLTypes"]=[{"CFBundleURLName":BUNDLE,"CFBundleURLSchemes":["youtubevanced",BUNDLE]}]
  info["UIBackgroundModes"]=sorted(set(info.get("UIBackgroundModes",[])+["audio"]))
  path.write_bytes(plistlib.dumps(info,fmt=plistlib.FMT_BINARY,sort_keys=False))
  dest=app/"Frameworks/VancedLocalProfile.dylib"
  dest.parent.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(profile,dest)
  subprocess.run([sys.executable,str(ytkace_root/"Tools/macho_inject.py"),str(app/"YouTube"),"--add-load","@rpath/VancedLocalProfile.dylib"],check=True)
  subprocess.run(["bash",str(ytkace_root/"Scripts/sign-bundle.sh"),str(app)],check=True)
  out.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for f in sorted((work/"Payload").rglob("*")):
    if f.is_file():z.write(f,f.relative_to(work))
 with zipfile.ZipFile(out) as z:
  check_zip(z)
  info=plistlib.loads(z.read(ROOT+"Info.plist"))
  if info["CFBundleIdentifier"]!=BUNDLE or info["CFBundleShortVersionString"]!=VERSION:raise ValueError("final identity changed")
  for name in ("YTKACE","VancedLocalProfile"):
   if ROOT+"Frameworks/"+name+".dylib" not in z.namelist():raise ValueError("missing tweak "+name)
  sys.path.insert(0,str(Path(__file__).resolve().parent))
  import verify_source
  imported=verify_source.macho(z.read(ROOT+"YouTube"))["imports"]
  for load in ("@rpath/YTKACE.dylib","@rpath/VancedLocalProfile.dylib"):
   if load not in imported:raise ValueError("required load command absent: "+load)
  report={"status":"STATIC_PASS_DEVICE_UNTESTED","version":VERSION,"bundle_id":BUNDLE,
          "original_sha256":SOURCE_HASH,"output_sha256":hashfile(out),"entries":len(z.namelist()),
          "custom_imports":[s for s in imported if s.endswith(("YTKACE.dylib","VancedLocalProfile.dylib"))],
          "signed":"requires personal signing in Sideloadly",
          "malware_safety":"NOT CERTIFIED - third-party decrypted source; antivirus only catches known signatures",
          "feature_runtime":"UNTESTED on iOS 27"}
 out.with_suffix(".audit.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for arg in ("source","intermediate","profile","ytkace_root","output"):p.add_argument("--"+arg.replace("_","-"),required=True,type=Path)
 a=p.parse_args()
 package(a.source,a.intermediate,a.profile,a.ytkace_root,a.output)
