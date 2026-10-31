#!/usr/bin/env python3
"""Discover candidate fixed-width regions in original IDF ZIP entries.

Read-only, no extraction, no execution, no interpretation of unknown fields.
The observed equal-byte rates are statistical signals, not schema proofs.
"""
import argparse
import json
import re
import zipfile
from pathlib import Path
import numpy as np

PERIODS=(17,19,21)
MAX_SAMPLE=131072

def inspect_zip_files(folder: Path):
    samples=[]
    for archive in sorted(folder.glob("autodata_part_*.zip")):
        if archive.name=="autodata_part_0016.zip":
            continue  # provider block is not bypassed
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                if not re.search(r"\.idf(?:\.chunk\d{4})?$",member.filename,re.I):
                    continue
                if member.flag_bits & 1 or member.file_size>1024**3:
                    continue
                with zf.open(member) as stream:
                    data=np.frombuffer(stream.read(min(MAX_SAMPLE,member.file_size)),dtype=np.uint8)
                if len(data)<512:
                    continue
                scores={str(lag):round(float(np.mean(data[:-lag]==data[lag:])),5) for lag in PERIODS}
                best=max(scores,key=scores.get)
                row={"path":member.filename,"package":archive.name,
                     "sample_bytes":len(data),"lag_scores":scores,
                     "best_lag":int(best),"best_score":scores[best]}
                if scores[best]>.1:
                    lag=int(best)
                    equal=data[:-lag]==data[lag:]
                    row["per_residue_lag_match"]=[
                        round(float(np.mean(equal[i::lag])),5)
                        for i in range(lag)]
                    # Generic 8-byte repeating-field hypothesis, NOT yet semantic.
                    row["candidate_8byte_field"]=all(p>.65 for p in row["per_residue_lag_match"][:8])
                samples.append(row)
    return {"original_programs_executed":False,
            "sample_cap":MAX_SAMPLE,
            "entries_with_512_or_more_sample_bytes":len(samples),
            "candidates":[r for r in samples if r["best_score"]>.1],
            "all_samples":samples}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source_zip_folder",type=Path)
    p.add_argument("--output",type=Path,default=Path("autodata_idf_periodicity.json"))
    args=p.parse_args()
    report=inspect_zip_files(args.source_zip_folder)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="all_samples"},indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
