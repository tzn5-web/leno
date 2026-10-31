"""Aggregate exact IDF header-prefix families from a private static-audit CSV.

This read-only tool does not decode IDF, inspect licenses, or run original code.
Only aggregate counts and a CSV digest leave the private workspace. The input
CSV can contain proprietary bytes and must never be committed to a public repo.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import defaultdict
from pathlib import Path

MAX_CSV_BYTES = 4 * 1024 * 1024
MAX_ROWS = 10000
PREFIX_LENGTHS = (4, 8, 16, 32)
REQUIRED = {"path", "category", "header64_hex", "sample_entropy"}


def analyze(raw: bytes, expected_sha256: str) -> dict:
    if not isinstance(raw, bytes) or len(raw) > MAX_CSV_BYTES:
        raise ValueError("Input CSV exceeds size bound or is not bytes")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(
            c not in "0123456789abcdefABCDEF" for c in expected_sha256):
        raise ValueError("Expected CSV SHA256 must be 64 hex characters")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("Private CSV SHA256 mismatch")
    try:
        source = io.StringIO(raw.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(source, strict=True)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError("Required audit columns missing")
        headers = []
        entropies = []
        names = set()
        rows = 0
        for item in reader:
            rows += 1
            if rows > MAX_ROWS:
                raise ValueError("Too many CSV rows")
            if item.get("category", "").lower() != "idf":
                continue
            name = item.get("path", "")
            if not name or name in names:
                raise ValueError("Missing or duplicate private IDF path")
            names.add(name)
            sample = item.get("header64_hex", "").strip().lower()
            if (not sample or len(sample) > 128 or len(sample) % 2 or
                    any(c not in "0123456789abcdef" for c in sample)):
                raise ValueError("Invalid bounded header hex sample")
            entropy = float(item.get("sample_entropy", "nan"))
            if not math.isfinite(entropy) or not 0 <= entropy <= 8:
                raise ValueError("Invalid sample entropy")
            headers.append(bytes.fromhex(sample))
            entropies.append(entropy)
    except (UnicodeDecodeError, csv.Error, TypeError, OverflowError) as exc:
        raise ValueError("Malformed private CSV") from exc
    if not headers:
        raise ValueError("No IDF records in private CSV")
    clusters = {}
    for length in PREFIX_LENGTHS:
        groups = defaultdict(int)
        for sample in headers:
            if len(sample) >= length:
                groups[sample[:length]] += 1
        sizes = sorted((count for count in groups.values() if count >= 2), reverse=True)
        clusters[str(length)] = {
            "multi_file_groups": len(sizes),
            "files_in_groups": sum(sizes),
            "group_sizes": sizes,
            "eligible_headers": sum(len(sample) >= length for sample in headers),
        }
    return {
        "schema": "atelierdata-idf-header-family-aggregate-v1",
        "source_csv_sha256": digest,
        "idf_records": len(headers),
        "headers_shorter_than_32_bytes": sum(len(sample) < 32 for sample in headers),
        "sample_entropy_at_least_7_9": sum(value >= 7.9 for value in entropies),
        "prefix_clusters_by_bytes": clusters,
        "original_files_executed": False,
        "idf_decoding_proven": False,
        "original_file_sha256_reverified": False,
        "limitations": (
            "Derived from a prior private static-audit CSV; source IDF bytes and "
            "original file SHA256 are not independently rechecked by this tool. "
            "Matching prefixes indicate shared bytes, not a decoded record "
            "format; high entropy does not establish encryption."
        ),
    }


def run(input_csv: Path, expected_sha256: str, public_output: Path) -> dict:
    input_csv, public_output = Path(input_csv), Path(public_output)
    if input_csv.resolve() == public_output.resolve():
        raise ValueError("Public output cannot overwrite private input")
    with input_csv.open("rb") as stream:
        raw = stream.read(MAX_CSV_BYTES + 1)
    result = analyze(raw, expected_sha256)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--public-output", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.input_csv, args.expected_sha256, args.public_output)
    print("IDF_HEADER_FAMILY_AUDIT=PASS idf_records=" + str(report["idf_records"]))


if __name__ == "__main__":
    main()
