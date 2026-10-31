"""SHA256-gated, aggregate-only signature triage of private IDF header CSV.

Read-only interoperability research. No IDF decoding, executable execution,
DRM interaction or proprietary header/path disclosure. A matching magic byte
pattern is a *candidate*, not proof of a container or decoder.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000
MAX_HEADER_BYTES = 64
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
HEX_RE = re.compile(r"[0-9a-fA-F]*\Z")
# Only well-known signatures; short matches can be coincidental.
SIGNATURES = {
    "zip": (bytes.fromhex("504b0304"), bytes.fromhex("504b0506"), bytes.fromhex("504b0708")),
    "gzip": (bytes.fromhex("1f8b08"),),
    "bzip2": (b"BZh",),
    "xz": (bytes.fromhex("fd377a585a00"),),
    "zstd": (bytes.fromhex("28b52ffd"),),
    "lz4_frame": (bytes.fromhex("04224d18"),),
    "7zip": (bytes.fromhex("377abcaf271c"),),
    "rar": (bytes.fromhex("526172211a0700"),),
    "sqlite": (b"SQLite format 3\x00",),
    "pdf": (b"%PDF-",),
    "png": (bytes.fromhex("89504e470d0a1a0a"),),
    "ole_cfb": (bytes.fromhex("d0cf11e0a1b11ae1"),),
    "cab": (b"MSCF",),
    "elf": (bytes.fromhex("7f454c46"),),
}
REQUIRED = {"path", "category", "header64_hex", "sample_entropy"}


def _zlib_compatible(header):
    if len(header) < 2:
        return False
    cmf, flg = header[:2]
    return (cmf & 15) == 8 and (cmf >> 4) <= 7 and ((cmf << 8) | flg) % 31 == 0


def analyze_csv(source: Path, expected_sha256: str):
    source = Path(source)
    if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
        raise ValueError("Expected SHA256 must be 64 hex characters")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Input must be a regular non-linked CSV")
    size = source.stat().st_size
    if size == 0 or size > MAX_CSV_BYTES:
        raise ValueError("Input CSV size outside limit")
    data = source.read_bytes()
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected_sha256.lower():
        raise ValueError("Private CSV SHA256 mismatch")
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Input CSV must be UTF-8") from exc
    reader = csv.DictReader(content.splitlines())
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError("Missing required CSV columns")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("Duplicate CSV columns")
    counts_zero = collections.Counter()
    counts_embedded = collections.Counter()
    rows = 0
    idf_rows = 0
    short_headers = 0
    high_entropy = 0
    zlib_compatible = 0
    no_known_magic = 0
    seen = set()
    for row in reader:
        rows += 1
        if rows > MAX_ROWS:
            raise ValueError("Too many CSV rows")
        if None in row:
            raise ValueError("Malformed CSV row")
        if (row.get("category") or "").strip().casefold() != "idf":
            continue
        idf_rows += 1
        name = (row.get("path") or "").strip()
        if not name or "\x00" in name or name.casefold() in seen:
            raise ValueError("Missing or duplicate private IDF path")
        seen.add(name.casefold())
        hex_value = (row.get("header64_hex") or "").strip()
        if len(hex_value) > 2 * MAX_HEADER_BYTES or len(hex_value) % 2 or not HEX_RE.fullmatch(hex_value):
            raise ValueError("Invalid IDF header hex")
        header = bytes.fromhex(hex_value)
        if len(header) < MAX_HEADER_BYTES:
            short_headers += 1
        try:
            entropy = float((row.get("sample_entropy") or "").strip())
        except ValueError as exc:
            raise ValueError("Invalid IDF entropy") from exc
        if not math.isfinite(entropy) or not 0 <= entropy <= 8:
            raise ValueError("IDF entropy outside 0..8")
        high_entropy += int(entropy >= 7.9)
        zlib_compatible += int(_zlib_compatible(header))
        any_magic = False
        for kind, patterns in SIGNATURES.items():
            if any(header.startswith(pattern) for pattern in patterns):
                counts_zero[kind] += 1
                any_magic = True
            if any(header.find(pattern, 1) >= 1 for pattern in patterns):
                counts_embedded[kind] += 1
                any_magic = True
        no_known_magic += int(not any_magic)
    if idf_rows == 0:
        raise ValueError("No IDF header records")
    return {
        "schema": "atelierdata-idf-signature-aggregate-v1",
        "input_csv_sha256_verified": True,
        "csv_rows": rows,
        "idf_header_records": idf_rows,
        "shorter_than_64_byte_headers": short_headers,
        "sample_entropy_ge_7_9": high_entropy,
        "zlib_header_compatible_at_zero": zlib_compatible,
        "known_magic_at_offset_zero": dict(sorted(counts_zero.items())),
        "known_magic_at_nonzero_offset": dict(sorted(counts_embedded.items())),
        "no_known_magic_in_first64": no_known_magic,
        "target_executed": False,
        "idf_decoder_proven": False,
        "limitations": "First 64 bytes only; matching signatures or zlib-compatible headers may be coincidental. No format, encryption, compression or decoder established. CSV hash verification does not independently verify original IDF files."
    }


def write_public(report, source: Path, destination: Path):
    source, destination = Path(source), Path(destination)
    if destination.is_symlink() or source.resolve() == destination.resolve():
        raise ValueError("Public output must not overwrite private input or a symlink")
    if not destination.parent.is_dir():
        raise ValueError("Public output directory does not exist")
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", prefix=".idf-signatures-", suffix=".tmp", dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        if destination.is_symlink():
            raise ValueError("Public output became a symlink")
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    if args.public_output.is_symlink() or args.input_csv.resolve() == args.public_output.resolve():
        parser.error("Public output must differ from private input")
    result = analyze_csv(args.input_csv, args.expected_sha256)
    write_public(result, args.input_csv, args.public_output)
    print("IDF_SIGNATURE_EVIDENCE=PASS (static metadata only; no decoder)")


if __name__ == "__main__":
    main()
