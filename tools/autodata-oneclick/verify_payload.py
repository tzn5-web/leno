#!/usr/bin/env python3
"""Validate original Autodata ADCDA2 files against every SHA256 chunk in INVENTAR.json."""
import argparse,hashlib,json,sys
from pathlib import Path,PurePosixPath

PREFIX="Autodata__3.45/ADCDA2/"
EXPECTED_RAR_SHA="e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da"
EXPECTED_ADBCD_SHA="a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4"
RISKY_NAME=("keygen","emulator","crack","patcher","dseo")
def validate(root:Path,manifest:dict,production=False):
    if manifest.get("archive")!="Autodata__3.45.rar":
        raise ValueError("MANIFEST_INVALID_ARCHIVE")
    if production:
        if (manifest.get("sha256","").lower()!=EXPECTED_RAR_SHA or
            manifest.get("original_bytes")!=2284074345 or
            manifest.get("file_count")!=139 or
            manifest.get("package_count")!=16):
            raise ValueError("PRODUCTION_ORIGINAL_MANIFEST_IDENTITY_MISMATCH")
    program=root/"ADCDA2"
    if not program.is_dir() or not (program/"ADBCD.exe").is_file():
        raise ValueError("SOURCE_INVALID_NO_ADBCD")
    relevant=[f for f in manifest["files"] if f["path"].startswith(PREFIX)]
    if not relevant:raise ValueError("MANIFEST_NO_PROGRAM")
    if production:
        if len(relevant)!=105:raise ValueError("PRODUCTION_PROGRAM_FILE_COUNT_MISMATCH")
        exe=next((x for x in relevant if x["path"]==PREFIX+"ADBCD.exe"),None)
        if exe is None or exe["size_bytes"]!=18102272 or len(exe["chunks"])!=1 or exe["chunks"][0]["sha256"].lower()!=EXPECTED_ADBCD_SHA:
            raise ValueError("PRODUCTION_ADBCD_IDENTITY_MISMATCH")
    listed=set()
    count=0
    for f in relevant:
        relative=f["path"][len(PREFIX):]
        parts=PurePosixPath(relative).parts
        if (not parts or "." in parts or ".." in parts or relative.startswith("/") or
            "\\" in relative or ":" in relative or
            any(part.rstrip(" .")!=part for part in parts)):
            raise ValueError("UNSAFE_RELATIVE_PATH:"+relative)
        if any(token in relative.lower() for token in RISKY_NAME):
            raise ValueError("RISKY_CONTENT:"+relative)
        if relative in listed:
            raise ValueError("DUPLICATE_PATH:"+relative)
        listed.add(relative)
        path=program.joinpath(*parts)
        if not path.resolve().is_relative_to(program.resolve()):
            raise ValueError("PATH_ESCAPES_PROGRAM:"+relative)
        if any(p.is_symlink() for p in [path,*path.parents] if p!=program and p!=root):
            raise ValueError("SYMLINK_IN_PROGRAM:"+relative)
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
    parser.add_argument("--production",action="store_true",help="Require original RAR and ADBCD manifest identities")
    args=parser.parse_args()
    obj=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    result=validate(args.source,obj,production=args.production)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("FILE_HASH_CHECK=PASS files="+str(result["program_files"]))
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("FILE_HASH_CHECK=FAIL",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(2)
