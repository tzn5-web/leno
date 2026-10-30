"""Bounded PE32 delay-import audit for authorized static interoperability research.

No target execution, DRM bypass, decompression, or IDF interpretation.
A delay-load directory is metadata: its presence does not prove any symbol
is called at runtime. Public output contains counts only; names and offsets
are restricted to an optional private report.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pe_file_io_xrefs import MAX_PE, parse_pe32, _u32

MAX_DESCRIPTORS = 256
MAX_THUNKS_PER_DESCRIPTOR = 2048
MAX_TOTAL_THUNKS = 8192
MAX_NAME_BYTES = 256
DELAY_DIRECTORY_INDEX = 13


def _name(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        raise ValueError("name pointer outside file")
    end = data.find(b"\0", offset, min(len(data), offset + MAX_NAME_BYTES + 1))
    if end < 0:
        raise ValueError("unterminated import name")
    raw = data[offset:end]
    if not raw or any(ch < 32 or ch > 126 for ch in raw):
        raise ValueError("invalid import name")
    return raw.decode("ascii")


def _mapper(data: bytes, pe: dict):
    header_at = _u32(data, 0x3c) + 24
    headers = _u32(data, header_at + 60)

    def map_rva(rva: int, length: int = 1) -> int:
        if rva < 0 or length < 1 or rva + length > 0x100000000:
            raise ValueError("invalid RVA")
        matches = []
        for section in pe["sections"]:
            delta = rva - section["rva"]
            if delta >= 0 and delta + length <= section["raw_size"]:
                offset = section["raw_at"] + delta
                if offset + length <= len(data):
                    matches.append(offset)
        if len(matches) > 1:
            raise ValueError("ambiguous overlapping PE sections")
        if matches:
            return matches[0]
        if rva + length <= min(headers, len(data)):
            return rva
        raise ValueError("unmapped RVA")
    return map_rva


def analyze_delay_imports(data: bytes, expected_sha256: str):
    if len(data) > MAX_PE:
        raise ValueError("PE exceeds maximum size")
    if len(expected_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in expected_sha256):
        raise ValueError("Expected SHA256 is mandatory")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("PE SHA256 mismatch")
    pe = parse_pe32(data)
    optional = _u32(data, 0x3c) + 24
    optional_size = struct.unpack_from("<H", data, optional - 4)[0]
    directory_count = _u32(data, optional + 92)
    directory_offset = optional + 96 + DELAY_DIRECTORY_INDEX * 8
    issues = Counter()
    details = []
    modes = Counter()
    resolved_symbols = 0
    descriptor_count = 0
    map_rva = _mapper(data, pe)
    if directory_count <= DELAY_DIRECTORY_INDEX or directory_offset + 8 > optional + optional_size:
        rva, size = 0, 0
    else:
        rva, size = struct.unpack_from("<II", data, directory_offset)

    if rva and size:
        if size < 32:
            issues["directory_too_small"] += 1
        else:
            try:
                first = map_rva(rva, 32)
            except ValueError:
                issues["directory_unmapped"] += 1
            else:
                terminated = False
                for idx in range(min(size // 32, MAX_DESCRIPTORS)):
                    at = first + idx * 32
                    try:
                        if map_rva(rva + idx * 32, 32) != at:
                            raise ValueError("descriptor crosses mapping")
                        values = struct.unpack_from("<8I", data, at)
                    except (ValueError, struct.error):
                        issues["descriptor_unmapped"] += 1
                        break
                    if not any(values):
                        terminated = True
                        break
                    descriptor_count += 1
                    attrs, name_ptr, hmod, iat, int_ptr, bound, unload, stamp = values
                    is_rva = bool(attrs & 1)
                    mode = "RVA" if is_rva else "VA"
                    modes[mode] += 1
                    row = {"index": idx, "pointer_mode": mode,
                           "descriptor_file_offset": at, "dll": None,
                           "symbols": [], "issues": []}
                    if attrs & ~1:
                        row["issues"].append("unknown_descriptor_flags")
                    def pointer_rva(value: int) -> int:
                        if not value:
                            raise ValueError("null pointer")
                        if is_rva:
                            return value
                        if value < pe["image_base"]:
                            raise ValueError("VA below image base")
                        return value - pe["image_base"]
                    try:
                        row["dll"] = _name(data, map_rva(pointer_rva(name_ptr)))
                    except ValueError:
                        row["issues"].append("dll_name_unmapped")
                    try:
                        thunk_rva = pointer_rva(int_ptr)
                        for n in range(MAX_THUNKS_PER_DESCRIPTOR):
                            if resolved_symbols >= MAX_TOTAL_THUNKS:
                                row["issues"].append("global_thunk_limit")
                                break
                            thunk = _u32(data, map_rva(thunk_rva + n * 4, 4))
                            if not thunk:
                                break
                            if thunk & 0x80000000:
                                symbol = "#" + str(thunk & 0xffff)
                            else:
                                symbol = _name(data, map_rva(pointer_rva(thunk) + 2))
                            row["symbols"].append(symbol)
                            resolved_symbols += 1
                        else:
                            row["issues"].append("thunk_limit")
                    except ValueError:
                        row["issues"].append("thunk_unmapped")
                    for issue in row["issues"]:
                        issues[issue] += 1
                    details.append(row)
                if not terminated:
                    issues["missing_terminator_or_truncated_directory"] += 1
                if size // 32 > MAX_DESCRIPTORS:
                    issues["descriptor_limit"] += 1
    state = ("ABSENT" if not (rva and size) else
             "PARTIAL" if issues else "PARSED")
    public = {
        "schema": "atelierdata-pe-delay-import-public-v1",
        "sha256": digest, "format": "PE32 x86",
        "delay_directory_declared": bool(rva and size),
        "descriptor_count": descriptor_count,
        "resolved_symbol_count": resolved_symbols,
        "pointer_mode_counts": dict(sorted(modes.items())),
        "issue_counts": dict(sorted(issues.items())),
        "state": state,
        "target_executed": False, "idf_decoder_proven": False,
        "limitations": ("Static directory parse only; malformed directories and "
                        "protected binaries can create misleading metadata. "
                        "No runtime call or IDF format is established.")
    }
    private = {"schema": "atelierdata-pe-delay-import-private-v1",
               "sha256": digest, "descriptors": details}
    return public, private


def run(pe_path, expected_sha256, public_path, private_path=None):
    pe_path, public_path = Path(pe_path), Path(public_path)
    if private_path is not None and Path(private_path).resolve() == public_path.resolve():
        raise ValueError("Public and private outputs must differ")
    with pe_path.open("rb") as fh:
        data = fh.read(MAX_PE + 1)
    public, private = analyze_delay_imports(data, expected_sha256)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    if private_path is not None:
        private_path = Path(private_path)
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_text(json.dumps(private, indent=2) + "\n", encoding="utf-8")
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pe", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--public-output", required=True, type=Path)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args()
    result = run(args.pe, args.expected_sha256, args.public_output, args.private_output)
    print("PE_DELAY_IMPORT_AUDIT=" + result["state"] +
          " descriptors=" + str(result["descriptor_count"]) +
          " symbols=" + str(result["resolved_symbol_count"]))


if __name__ == "__main__":
    main()
