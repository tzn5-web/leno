#!/usr/bin/env python3
"""Read-only cross-index analysis for user-supplied Autodata 3.45 ZIP entries.

Records are *opaque* bytes, not decoded automotive data. Reports aggregates
only, never original 8-byte token values or file contents.
"""
from __future__ import annotations
import argparse
import json
import math
import zipfile
from pathlib import Path

ROOT = "Autodata__3.45/ADCDA2/COMMON/"
CONFIG = {
    "FAS.IDF": ("autodata_part_0001.zip", 19),
    "MIDS.IDF": ("autodata_part_0001.zip", 17),
    "MIDTDoc.IDF": ("autodata_part_0001.zip", 17),
    "SGINT.IDF": ("autodata_part_0001.zip", 21),
    "SGOPS.IDF": ("autodata_part_0002.zip", 21),
}

def read_prefix(folder: Path, package: str, entry: str, limit: int = 900_000):
    with zipfile.ZipFile(folder / package) as archive:
        with archive.open(ROOT + entry) as stream:
            return stream.read(limit)

def table_groups(data: bytes, width: int, key_width: int = 8,
                 stop_after_nonrepeats: int = 1024):
    """Candidate prefix ends after last adjacent-key match before long dry run.

    This is an empirical boundary hypothesis, NOT a validated file schema.
    """
    rows = [data[i:i+key_width]
            for i in range(0, len(data)-width+1, width)]
    equal = [a == b for a,b in zip(rows,rows[1:])]
    streak, cutoff = 0, None
    for i,same in enumerate(equal):
        streak = 0 if same else streak+1
        if streak >= stop_after_nonrepeats:
            last = [j for j,flag in enumerate(equal[:i+1]) if flag]
            if not last:
                raise ValueError("No repeated table-like keys found")
            cutoff = last[-1]+2
            break
    if cutoff is None:
        raise ValueError("Insufficient sample for candidate boundary")
    if any(equal[cutoff:]):
        raise ValueError("Later repeated keys conflict with boundary")
    groups = []
    for key in rows[:cutoff]:
        if not groups or groups[-1][0] != key:
            groups.append([key,1])
        else:
            groups[-1][1]+=1
    if len({key for key,_ in groups})!=len(groups):
        raise ValueError("Key is non-contiguous in candidate prefix")
    return groups, {
        "candidate_rows":cutoff,"candidate_bytes":cutoff*width,
        "candidate_width":width,"groups":len(groups),
        "unique_opaque_keys":len(groups),
        "long_zero_match_streak_checked":stop_after_nonrepeats,
        "boundary_is_inferred_not_proven":True
    }

def pearson(a,b):
    if len(a)<2 or len(a)!=len(b):return None
    am,bm=sum(a)/len(a),sum(b)/len(b)
    cov=sum((x-am)*(y-bm) for x,y in zip(a,b))
    scale=math.sqrt(sum((x-am)**2 for x in a)*sum((y-bm)**2 for y in b))
    return cov/scale if scale else None

def compare_groups(first,second):
    A={k:(i,n) for i,(k,n) in enumerate(first)}
    B={k:(i,n) for i,(k,n) in enumerate(second)}
    shared=sorted(set(A)&set(B),key=lambda k:A[k][0])
    order=[B[k][0] for k in shared]
    corr=pearson([A[k][1] for k in shared],[B[k][1] for k in shared])
    return {
        "shared_opaque_keys":len(shared),
        "all_shared_keys_in_same_order":(
            all(x<y for x,y in zip(order,order[1:])) if shared else None),
        "group_size_pearson":round(corr,8) if corr is not None else None,
        "first_unique_groups":len(first),"second_unique_groups":len(second),
        "group_count_A_only":len(first)-len(shared),
        "group_count_B_only":len(second)-len(shared),
        "key_semantics":"unknown; exact shared 8-byte values only"
    }

def audit(folder:Path):
    groups,summaries={},{}
    for name,(package,width) in CONFIG.items():
        try:
            data=read_prefix(folder,package,name)
            g,metadata=table_groups(data,width)
            groups[name]=g
            summaries[name]=metadata
        except Exception as exc:
            summaries[name]={"error":str(exc),"type":type(exc).__name__}
    comparisons={}
    for a,b in [("MIDS.IDF","MIDTDoc.IDF"),("SGINT.IDF","SGOPS.IDF"),
                ("FAS.IDF","MIDS.IDF"),("MIDS.IDF","SGINT.IDF")]:
        if a in groups and b in groups:
            comparisons[a+" :: "+b]=compare_groups(groups[a],groups[b])
    return {
        "sources":"Original archive ZIP entries, examined statically",
        "original_programs_executed":False,
        "archive_security_bypass":False,
        "method":"Candidate fixed-width prefix and exact opaque 8-byte token joins",
        "table_candidates":summaries,
        "cross_file_relationships":comparisons,
        "limitation":"Opaque tokens and candidate widths do not decode automotive semantics"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("zip_folder",type=Path)
    p.add_argument("--output",type=Path,default=Path("autodata_idf_cross_index.json"))
    args=p.parse_args()
    result=audit(args.zip_folder)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
