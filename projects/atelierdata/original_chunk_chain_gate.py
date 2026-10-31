"""Manifest-only structural audit of split Autodata archive members.

No ZIP access, IDF reconstruction/decoding, binary execution, license or DRM work.
Only aggregate statistics are emitted; private inventory remains outside GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from original_archive_preflight import BLOCKED_PACKAGE, load_manifest

CHUNK_BYTES = 64 * 1024 * 1024
SCHEMA = "atelierdata-original-chunk-chain-gate-v1"
PACKAGE_NUMBER = re.compile(r"autodata_part_([0-9]{4})\.zip\Z")


def audit_manifest(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path)
    manifest, entries = load_manifest(manifest_path)
    failures = []
    multipart_files = 0
    multipart_chunks = 0
    idf_files = 0
    idf_chunks = 0
    blocked_chunks = 0
    blocked_idf_files = 0
    crossing_package_boundaries = 0
    max_chain = 0
    for row in manifest["files"]:
        path = row["path"]
        chunks = row["chunks"]
        is_idf = path.casefold().endswith(".idf")
        idf_files += is_idf
        idf_chunks += len(chunks) if is_idf else 0
        blocked = any(c["package"] == BLOCKED_PACKAGE for c in chunks)
        blocked_idf_files += bool(is_idf and blocked)
        blocked_chunks += sum(c["package"] == BLOCKED_PACKAGE for c in chunks)
        if len(chunks) == 1:
            if chunks[0]["entry"] != path:
                failures.append("single_member_entry_name_mismatch")
            continue
        multipart_files += 1
        multipart_chunks += len(chunks)
        max_chain = max(max_chain, len(chunks))
        package_numbers = []
        for index, chunk in enumerate(chunks):
            if chunk["entry"] != f"{path}.chunk{index:04d}":
                failures.append("multipart_sequence_name_or_order_mismatch")
            match = PACKAGE_NUMBER.fullmatch(chunk["package"])
            if match is None:
                failures.append("invalid_package_number")
            else:
                package_numbers.append(int(match.group(1)))
            size = chunk["bytes"]
            if index < len(chunks) - 1 and size != CHUNK_BYTES:
                failures.append("nonfinal_chunk_size_mismatch")
            if index == len(chunks) - 1 and not 0 < size <= CHUNK_BYTES:
                failures.append("final_chunk_size_out_of_bounds")
        if package_numbers != sorted(package_numbers):
            failures.append("package_order_regression")
        crossing_package_boundaries += len(set(c["package"] for c in chunks)) > 1
    expected_count = manifest.get("file_count")
    if expected_count is not None and expected_count != len(manifest["files"]):
        failures.append("declared_file_count_mismatch")
    declared_total = manifest.get("total_extracted_bytes")
    if declared_total is not None and declared_total != sum(x["size_bytes"] for x in manifest["files"]):
        failures.append("declared_total_bytes_mismatch")
    package_count = len({package for package, _ in entries})
    if manifest.get("package_count") is not None and manifest["package_count"] != package_count:
        failures.append("declared_package_count_mismatch")
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "schema": SCHEMA,
        "manifest_sha256": manifest_digest,
        "manifest_file_count": len(manifest["files"]),
        "manifest_chunk_count": len(entries),
        "manifest_package_count": package_count,
        "single_chunk_file_count": len(manifest["files"]) - multipart_files,
        "multipart_file_count": multipart_files,
        "multipart_chunk_count": multipart_chunks,
        "multipart_cross_package_file_count": crossing_package_boundaries,
        "largest_chunk_chain": max_chain,
        "idf_file_count": idf_files,
        "idf_chunk_count": idf_chunks,
        "blocked_package_chunk_count": blocked_chunks,
        "idf_files_requiring_blocked_package": blocked_idf_files,
        "structural_failures": sorted(set(failures)),
        "chain_structure": "PASS" if not failures else "FAIL",
        "zip_payloads_opened": False,
        "zip_member_sha256_rechecked": False,
        "original_executed": False,
        "idf_decoded": False,
        "vendor_authenticity_verified": False,
        "license_verified": False,
        "conclusion": "Manifest chain structure only; per-chunk SHA256 and whole-file bytes are not reverified.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() == args.manifest.resolve():
            raise ValueError("Refusing to overwrite source inventory")
        report = audit_manifest(args.manifest)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        print(payload)
        return 0 if report["chain_structure"] == "PASS" else 2
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": SCHEMA, "chain_structure": "FAIL", "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
