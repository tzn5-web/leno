"""Cross-check private, read-only Autodata audit *records* without opening archives.

Inputs stay on the owner's machine/Drive. Public output contains aggregate counts
only. A matching audit CSV is not proof of vendor authenticity, original license,
or a fresh SHA256 rehash of the underlying ZIP members.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from original_archive_preflight import BLOCKED_PACKAGE, load_manifest

HEX64 = re.compile(r"[a-fA-F0-9]{64}\Z")
SCHEMA = "atelierdata-original-evidence-ledger-v1"


def _csv_rows(path: Path, key: str) -> dict[str, dict]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or key not in reader.fieldnames:
            raise ValueError("Required CSV column missing")
        result = {}
        for row in reader:
            name = row.get(key)
            if not name or name in result:
                raise ValueError("Missing or duplicate CSV identity")
            result[name] = row
        return result


def _integer(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric audit field") from exc
    if parsed < 0:
        raise ValueError("Negative audit field")
    return parsed


def crosscheck(manifest_path: Path, reconstruction_csv: Path, downloads_csv: Path) -> dict:
    manifest, _ = load_manifest(manifest_path)
    expected = {row["path"]: row for row in manifest["files"]}
    packages = {c["package"] for row in expected.values() for c in row["chunks"]}
    reconstruction = _csv_rows(reconstruction_csv, "path")
    downloads = _csv_rows(downloads_csv, "name")
    if set(reconstruction) != set(expected):
        raise ValueError("Reconstruction audit rows do not match inventory")
    if "INVENTAR.json" not in downloads:
        raise ValueError("Missing manifest download record")
    manifest_bytes = Path(manifest_path).read_bytes()
    inventory = downloads.pop("INVENTAR.json")
    if (_integer(inventory.get("bytes")) != len(manifest_bytes)
        or inventory.get("sha256", "").lower() != hashlib.sha256(manifest_bytes).hexdigest()
        or inventory.get("status") != "downloaded"):
        raise ValueError("Manifest download evidence does not match current manifest")
    if not set(downloads) <= packages or BLOCKED_PACKAGE in downloads:
        raise ValueError("Unknown or explicitly blocked package in download ledger")
    for row in downloads.values():
        if (row.get("status") != "downloaded"
            or not HEX64.fullmatch(row.get("sha256") or "")
            or _integer(row.get("bytes")) == 0):
            raise ValueError("Invalid package download evidence")
    downloaded = set(downloads)
    pass_files = 0
    unavailable_files = 0
    idf_pass = 0
    directly_comparable_hashes = 0
    multichunk_not_independently_hash_comparable = 0
    for path, row in expected.items():
        audit = reconstruction[path]
        chunks = row["chunks"]
        if (_integer(audit.get("expected_size")) != row["size_bytes"]
            or _integer(audit.get("chunk_count")) != len(chunks)):
            raise ValueError("Audit size or chunk count disagrees with manifest")
        present = all(c["package"] in downloaded for c in chunks)
        status = audit.get("status")
        if present:
            if (status != "PASS" or _integer(audit.get("actual_size")) != row["size_bytes"]
                or audit.get("problems", "").strip()):
                raise ValueError("Available file has inconsistent audit PASS evidence")
            digest = audit.get("sha256_reconstructed") or ""
            if not HEX64.fullmatch(digest):
                raise ValueError("Missing or invalid reconstructed SHA256")
            if len(chunks) == 1:
                if digest.lower() != chunks[0]["sha256"].lower():
                    raise ValueError("Single-chunk hash disagrees with manifest")
                directly_comparable_hashes += 1
            else:
                # The manifest has per-chunk hashes, not a full-file hash.
                # The CSV's reconstructed digest cannot be independently
                # confirmed without reading and hashing the original chunks.
                multichunk_not_independently_hash_comparable += 1
            pass_files += 1
            if path.lower().endswith(".idf"):
                idf_pass += 1
        else:
            if (status != "FAIL_OR_UNAVAILABLE"
                or _integer(audit.get("actual_size")) != 0
                or audit.get("sha256_reconstructed", "").strip()):
                raise ValueError("Unavailable file was incorrectly marked verified")
            unavailable_files += 1
    return {
        "schema": SCHEMA,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest_files": len(expected),
        "manifest_packages": len(packages),
        "downloaded_package_records": len(downloaded),
        "blocked_package_record_present": BLOCKED_PACKAGE in downloaded,
        "reconstruction_pass_records_consistent": pass_files,
        "reconstruction_unavailable_records_consistent": unavailable_files,
        "idf_pass_records_consistent": idf_pass,
        "single_chunk_reconstructed_hashes_matching_manifest": directly_comparable_hashes,
        "multichunk_full_hashes_not_comparable_to_manifest": multichunk_not_independently_hash_comparable,
        "record_consistency": "PASS",
        "archives_opened_in_this_run": False,
        "bytes_rehashed_in_this_run": False,
        "original_executed": False,
        "license_verified": False,
        "vendor_authenticity_verified": False,
        "idf_decoded": False,
        "original_windows_installation_ready": False,
        "interpretation": "This is a consistency check of previously recorded audit evidence. "
                          "It does not independently rehash original archives or prove their authenticity.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reconstruction-csv", type=Path, required=True)
    parser.add_argument("--downloads-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = crosscheck(args.manifest, args.reconstruction_csv, args.downloads_csv)
        encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            inputs = {p.resolve() for p in
                      (args.manifest, args.reconstruction_csv, args.downloads_csv)}
            if args.output.resolve() in inputs:
                raise ValueError("Output would overwrite private input")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded)
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        # Do not echo private file paths or proprietary audit CSV rows.
        print(json.dumps({"schema": SCHEMA, "record_consistency": "FAIL",
                          "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
