#!/usr/bin/env python3
"""Read-only IDF sample comparison from ZIPs; never execute archived code.

Emits metadata only. No IDF format/decryption claim is made.
"""
import argparse
import collections
import hashlib
import itertools
import json
import math
import re
import zipfile
from pathlib import Path

MAGIC = {
    "gzip": bytes.fromhex("1f8b"), "zlib": bytes.fromhex("789c"),
    "zlib_high": bytes.fromhex("78da"), "zip": b"PK\x03\x04",
    "sqlite": b"SQLite format 3\x00", "ole": bytes.fromhex("d0cf11e0a1b11ae1"),
    "png": b"\x89PNG\r\n\x1a\n", "bmp": b"BM", "pdf": b"%PDF",
}

def entropy(data):
    if not data:
        return 0.0
    n = len(data)
    return round(-sum((v/n)*math.log2(v/n) for v in collections.Counter(data).values()), 4)

def common_prefix(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))

def similarity(a, b):
    n = min(len(a), len(b))
    return sum(x == y for x, y in zip(a[:n], b[:n])) / n if n else 0.0

def read_samples(folder, cap=131072):
    records = []
    for path in sorted(Path(folder).glob("autodata_part_*.zip")):
        if path.name == "autodata_part_0016.zip":
            continue  # known provider block, not bypassed
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not re.search(r"\.idf(?:\.chunk\d{4})?$", info.filename, re.I):
                    continue
                if info.flag_bits & 1 or info.file_size > 1024**3:
                    continue
                with archive.open(info) as src:
                    sample = src.read(min(cap, info.file_size))
                records.append({
                    "package": path.name, "file": info.filename,
                    "bytes_total": info.file_size, "bytes_sampled": len(sample),
                    "entropy": entropy(sample),
                    "sample_sha256": hashlib.sha256(sample).hexdigest(),
                    "common_magic_at_start": [k for k, v in MAGIC.items() if sample.startswith(v)],
                    "sample": sample,
                })
    return records

def pe_string_triage(pe_path):
    if not pe_path:
        return None
    b = Path(pe_path).read_bytes()
    tokens = [".IDF", "TDGRAPH.IDF", "MODELS.IDF", "COMMON", "ReadFile",
              "CreateFileA", "GetProcAddress", "LoadLibraryA",
              "inflate 1.2.3", "incorrect header check"]
    report = {"size": len(b), "sha256": hashlib.sha256(b).hexdigest(),
              "MZ_header": b.startswith(b"MZ"), "string_offsets": {}}
    for token in tokens:
        report["string_offsets"][token] = {
            "ascii": [m.start() for m in re.finditer(re.escape(token.encode("ascii")), b)][:20],
            "utf16le": [m.start() for m in re.finditer(re.escape(token.encode("utf-16le")), b)][:20],
        }
    return report

def run(folder, pe=None, cap=131072, threshold=.08):
    records = read_samples(folder, cap)
    pairs = []
    for a, b in itertools.combinations(records, 2):
        length = min(len(a["sample"]), len(b["sample"]))
        if length < 4096:
            continue
        same_fraction = similarity(a["sample"], b["sample"])
        prefix = common_prefix(a["sample"], b["sample"])
        if same_fraction >= threshold or prefix >= 8:
            pairs.append({
                "a": a["file"], "b": b["file"],
                "a_package": a["package"], "b_package": b["package"],
                "compared_bytes": length,
                "same_offset_byte_fraction": round(same_fraction, 5),
                "common_prefix_bytes_within_sample": prefix,
            })
    pairs.sort(key=lambda p: (-p["same_offset_byte_fraction"], -p["common_prefix_bytes_within_sample"]))
    return {
        "method": "Read-only ZIP sample and equal-offset pair comparison",
        "original_programs_executed": False, "malware_bypass": False,
        "sample_cap": cap, "sample_entries": len(records),
        "distinct_logical_files": len({r["file"].split(".chunk")[0] for r in records}),
        "entries_entropy_ge_7_8": sum(r["entropy"] >= 7.8 for r in records),
        "common_magic_at_start": sum(bool(r["common_magic_at_start"]) for r in records),
        "pairs_over_threshold": pairs,
        "entries": [{k: v for k, v in r.items() if k != "sample"} for r in records],
        "pe": pe_string_triage(pe),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_folder", type=Path)
    parser.add_argument("--pe", type=Path, help="Optional, only static strings; no execution")
    parser.add_argument("--out", type=Path, default=Path("idf_similarity.json"))
    args = parser.parse_args()
    result = run(args.zip_folder, args.pe)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("entries", "pe")}, indent=2))
