#!/usr/bin/env python3
"""Inspect installation instructions as text. Never execute package scripts or binaries."""
import argparse,hashlib,json,subprocess
from pathlib import Path
DOCUMENT_EXT={".txt",".pdf",".cmd",".bat",".reg",".htm"}
MAX_BYTES=4_000_000
def hash_file(p):
    h=hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1048576),b""):h.update(chunk)
    return h.hexdigest()
def inspect(root):
    results=[]
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in DOCUMENT_EXT:continue
        entry={"name":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,
               "sha256":hash_file(p),"read_status":"not_read"}
        if p.stat().st_size>MAX_BYTES:
            entry["read_status"]="too_large"
        elif p.suffix.lower()==".pdf":
            try:
                proc=subprocess.run(["pdftotext","-layout",str(p),"-"],check=True,
                    capture_output=True,timeout=30)
                entry["text"]=proc.stdout.decode("utf-8","replace")[:200000]
                entry["read_status"]="pdf_text_only"
            except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                entry["read_status"]="pdf_unreadable_"+type(exc).__name__
        else:
            data=p.read_bytes()
            for enc in ("utf-8-sig","utf-16","cp1252"):
                try:
                    text=data.decode(enc);break
                except UnicodeDecodeError:pass
            else:text=data.decode("latin1","replace")
            entry["text"]=text[:200000]
            entry["read_status"]="text_only"
        results.append(entry)
    return results
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("--output",default="install_instruction_review.json")
    args=parser.parse_args()
    if not args.source.is_dir():raise SystemExit("SOURCE_NOT_FOUND")
    result={"mode":"inert_document_review","documents":inspect(args.source),
            "note":"No scripts or programs were executed. Text is untrusted."}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("INSTRUCTIONS_READ_ONLY_AUDIT=PASS count="+str(len(result["documents"])))
if __name__=="__main__":main()
