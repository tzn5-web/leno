#!/usr/bin/env python3
"""Read-only verifier for private Watch6T HOLO V5 layered package.
Usage: python Verify-HOLO-V5.py /path/to/Watch6T_HOLO_V5_COMPLET.zip
No ADB, Bluetooth, or watch connection is used.
"""
import argparse, io, json, hashlib, re, sys, zipfile
from collections import Counter
from PIL import Image

ROOT="assets/DialCustom/dial_1_circle_240x240/"
PACK="HOLO_V5_APK_TEMPLATE_CANDIDATE.zip"
def check(blob:bytes):
    with zipfile.ZipFile(io.BytesIO(blob)) as pack:
        assert pack.testzip() is None,"CRC error inside layered ZIP"
        paths=[n for n in pack.namelist() if n.startswith(ROOT)]
        assert len(paths)==248,f"Expected 248 entries, received {len(paths)}"
        groups=Counter(n[len(ROOT):].split("/")[0] for n in paths)
        for group in groups:
            prefix=ROOT+group+"/"
            cfg=[n for n in paths if n.startswith(prefix+"config_")]
            assert len(cfg)==1,(group,cfg)
            m=re.search(r"/config_(\d+)x(\d+)_(\d+)x(\d+)\.txt$",cfg[0])
            assert m,group
            w,h,x,y=map(int,m.groups())
            assert x>=0 and y>=0 and x+w<=240 and y+h<=240,(group,w,h,x,y)
            for filename in paths:
                if filename.startswith(prefix) and filename.endswith(".png"):
                    with Image.open(io.BytesIO(pack.read(filename))) as image:
                        assert image.size==(w,h),(filename,image.size,(w,h))
                        image.verify()
        assert sum(n.startswith(ROOT+"battery/") and n.endswith(".png") for n in paths)==5
        assert sum(n.startswith(ROOT+"stepproccess/") and n.endswith(".png") for n in paths)==11
    return dict(files=len(paths),families=len(groups),battery_frames=5,steps_progress_frames=11)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("package")
    args=p.parse_args()
    with zipfile.ZipFile(args.package) as archive:
        assert archive.testzip() is None
        manifest=json.loads(archive.read("MANIFEST.json"))
        binpack=archive.read(PACK)
        reported=next(x for x in manifest["outputs"] if x["file"]==PACK)
        assert hashlib.sha256(binpack).hexdigest()==reported["sha256"],"SHA256 mismatch"
        detail=check(binpack)
    print(json.dumps({"result":"PASS: structural only, NOT device compatible","detail":detail},indent=2))
if __name__=="__main__":main()
