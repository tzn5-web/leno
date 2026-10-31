#!/usr/bin/env python3
"""Autodata IDF: verify a candidate shared 21-byte record region (read-only).

Does not execute originals or decode/proclaim field semantics.
Requires autodata_part_0001.zip and autodata_part_0002.zip, both accessible
through normal authorized paths. Writes ONLY numeric/aggregate metadata.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

ENTRY_PREFIX="Autodata__3.45/ADCDA2/COMMON/"
BLOCK=21
KEY_LENGTH=8

def _read(zip_path: Path, entry: str, length: int = 2 * 1024 * 1024) -> bytes:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(entry) as stream:
            return stream.read(length)

def probe(folder: Path, max_bytes: int = 2 * 1024 * 1024) -> dict:
    a=_read(folder/"autodata_part_0001.zip",ENTRY_PREFIX+"SGINT.IDF",max_bytes)
    b=_read(folder/"autodata_part_0002.zip",ENTRY_PREFIX+"SGOPS.IDF",max_bytes)
    limit=min(len(a),len(b))
    if limit < 100000:
        raise ValueError("Not enough bytes to verify table: need >=100KB from each file")
    row_count=0
    # Determine first row where 8-byte field differs: a falsifiable block boundary.
    for off in range(0, limit - BLOCK + 1, BLOCK):
        if a[off:off+KEY_LENGTH]!=b[off:off+KEY_LENGTH]:
            break
        row_count+=1
    boundary=row_count*BLOCK
    keys_a=[a[i:i+KEY_LENGTH] for i in range(0,boundary,BLOCK)]
    keys_b=[b[i:i+KEY_LENGTH] for i in range(0,boundary,BLOCK)]
    assert keys_a==keys_b
    values_equal=sum(x==y for i in range(0,boundary,BLOCK)
                     for x,y in zip(a[i+KEY_LENGTH:i+BLOCK],b[i+KEY_LENGTH:i+BLOCK]))
    payload_bytes=row_count*(BLOCK-KEY_LENGTH)
    unique_keys=len(set(keys_a))
    followup=[]
    for start in [0,boundary,max(boundary+65536,131072),1048576]:
        if start+4096+BLOCK>limit:
            continue
        for label,data in [("SGINT",a),("SGOPS",b)]:
            window=data[start:start+4096]
            lag_matches=sum(x==y for x,y in zip(window[:-BLOCK],window[BLOCK:]))
            followup.append({"source":label,"offset":start,
                             "lag_21_match_fraction":round(lag_matches/(len(window)-BLOCK),6)})
    result={
        "method":"static zip-entry sample comparison",
        "source_a":"COMMON/SGINT.IDF",
        "source_b":"COMMON/SGOPS.IDF",
        "original_executable_executed":False,
        "fixed_21_byte_records_in_shared_prefix":row_count,
        "shared_prefix_length":boundary,
        "record_width":BLOCK,
        "identical_field_width":KEY_LENGTH,
        "different_field_width":BLOCK-KEY_LENGTH,
        "identical_8byte_field_count":len(keys_a),
        "distinct_8byte_field_values":unique_keys,
        "same_byte_fraction_in_13byte_regions":round(values_equal/payload_bytes,8) if payload_bytes else None,
        "same_13byte_region_count":sum(a[i+KEY_LENGTH:i+BLOCK]==b[i+KEY_LENGTH:i+BLOCK] for i in range(0,boundary,BLOCK)),
        "lag_21":followup,
        "interpretation":"Unidentified fixed-width shared region; semantics not proven. After boundary, pattern no longer assumed.",
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source_zip_folder",type=Path)
    p.add_argument("--output",type=Path,default=Path("autodata_sg_shared_records.json"))
    args=p.parse_args()
    result=probe(args.source_zip_folder)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
