#!/usr/bin/env python3
"""Validate original Autodata ADCDA2 files against every SHA256 chunk in INVENTAR.json."""
import argparse,hashlib,json,sys
from pathlib import Path,PurePosixPath

PREFIX="Autodata__3.45/ADCDA2/"
RISKY_NAME=("keygen","emulator","crack","patcher","dseo")
def validate(root:Path,manifest:dict):
    if manifest.get("archive")!="Autodata__3.45.rar":
        raise ValueError("MANIFEST_INVALID_ARCHIVE")
    program=root/"ADCDA2"
    if not program.is_dir() or not (program/"ADBCD.exe").is_file():
        raise ValueError("SOURCE_INVALID_NO_ADBCD")
    relevant=[f for f in manifest["files"] if f["path"].startswith(PREFIX)]
    if not relevant:raise ValueError("MANIFEST_NO_PROGRAM")
    listed=set()
    count=0
    for f in relevant:
        relative=f["path"][len(PREFIX):]
        parts=PurePosixPath(relative).parts
        if not parts or "." in parts or ".." in parts or relative.startswith("/"):
            raise ValueError("UNSAFE_RELATIVE_PATH:"+relative)
        if any(token in relative.lower() for token in RISKY_NAME):
            raise ValueError("RISKY_CONTENT:"+relative)
        if relative in listed:
            raise ValueError("DUPLICATE_PATH:"+relative)
        listed.add(relative)
        path=program.joinpath(*parts)
        if path.is_symlink() or not path.is_file():
            raise ValueError("MISSING_OR_SYMLINK:"+relative)
        if path.stat().st_size!=f["size_bytes"]:
            raise ValueError("SIZE_MISMATCH:"+relative)
        with path.open("rb") as stream:
            total=0
            for c in f["chunks"]:
                remaining=c["bytes"]
                h=hashlib.sha256()
                while remaining>0:
                    block=stream.read(min(remaining,1024*1024))
                    if not block:raise ValueError("SHORT_READ:"+relative)
                    h.update(block);remaining-=len(block);total+=len(block)
                if h.hexdigest()!=c["sha256"].lower():
                    raise ValueError("SHA256_MISMATCH:"+relative)
            if stream.read(1) or total!=f["size_bytes"]:
                raise ValueError("EXTRA_DATA:"+relative)
        count+=1
    actual={p.relative_to(program).as_posix() for p in program.rglob("*") if p.is_file()}
    if listed!=actual:
        raise ValueError("UNEXPECTED_FILES:"+";".join(sorted(actual-listed)[:10]))
    return {"status":"HASH_VERIFIED","program_files":count,
            "warning":"SHA integrity is not malware clearance or proof of a valid license"}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,type=Path,help="Parent directory containing ADCDA2")
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--output",default="payload_verification.json")
    args=parser.parse_args()
    obj=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    result=validate(args.source,obj)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("FILE_HASH_CHECK=PASS files="+str(result["program_files"]))
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("FILE_HASH_CHECK=FAIL",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(2)
