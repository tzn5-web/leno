"""Independent, SHA256-bound audit of *reported* Ghidra IDF xref sites.

Reads only a private PE32 and private/public Ghidra JSON reports. It does not
execute PE code, decode IDF, or verify Ghidra instruction boundaries. Output
contains aggregate counts only, never original bytes, offsets or addresses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from ghidra_idf_xref_verify import limited_json, verify
from pe_file_io_xrefs import MAX_PE, parse_pe32

SCHEMA = "atelierdata-idf-reference-sites-public-v1"
MAX_WINDOW = 16
ADDRESS = re.compile(r"(?:0x)?[0-9a-fA-F]{1,8}\Z")


def _address(value):
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise ValueError("Invalid Ghidra reference address")
    return int(value, 16)


def _locations(pe, data, va):
    rva = va - pe["image_base"]
    result = []
    for sec in pe["sections"]:
        delta = rva - sec["rva"]
        if 0 <= delta < sec["raw_size"]:
            offset = sec["raw_at"] + delta
            if offset < len(data):
                result.append((offset, sec, sec["raw_size"] - delta))
    return result


def audit(data: bytes, expected_sha: str, private: dict, public: dict) -> dict:
    """Classify file-backed Ghidra reference sources without asserting code flow."""
    prior = verify(data, expected_sha, private, public)
    pe = parse_pe32(data)
    total = mapped_exec = mapped_data = unmapped = ambiguous = 0
    raw_va_near = duplicates = unlisted = 0
    for key, rows in private["hits_with_addresses"].items():
        for hit in rows:
            target = _address(hit["address"])
            seen = set()
            references = hit["references_from"]
            unlisted += hit["reference_count"] - len(references)
            for ref in references:
                source = _address(ref)
                total += 1
                if source in seen:
                    duplicates += 1
                seen.add(source)
                places = _locations(pe, data, source)
                if not places:
                    unmapped += 1
                    continue
                if len(places) != 1:
                    ambiguous += 1
                    continue
                offset, section, available = places[0]
                if not section["executable"]:
                    mapped_data += 1
                    continue
                mapped_exec += 1
                # A nearby LE32 VA is a raw-byte observation, NOT proof that
                # the bytes form a decoded instruction or a control-flow edge.
                window = data[offset:offset + min(MAX_WINDOW, available)]
                if target.to_bytes(4, "little") in window:
                    raw_va_near += 1
    if total + unlisted != sum(
        hit["reference_count"]
        for rows in private["hits_with_addresses"].values() for hit in rows
    ):
        raise ValueError("Reference count accounting mismatch")
    return {
        "schema": SCHEMA,
        "pe_sha256_verified": hashlib.sha256(data).hexdigest(),
        "ghidra_evidence_consistency": prior["status"],
        "verified_literal_hits": prior["verified_literal_hits"],
        "reported_reference_sites_inspected": total,
        "reported_reference_sites_unlisted_due_to_cap": unlisted,
        "unique_source_repetitions": duplicates,
        "sources_in_executable_raw_sections": mapped_exec,
        "sources_in_nonexecutable_raw_sections": mapped_data,
        "sources_unmapped_to_raw_file": unmapped,
        "sources_with_ambiguous_raw_mapping": ambiguous,
        "executable_sources_with_nearby_raw_literal_va": raw_va_near,
        "original_executed": False,
        "ghidra_disassembly_independently_verified": False,
        "idf_loader_proven": False,
        "idf_decoder_proven": False,
        "interpretation": "Raw PE mappings and nearby pointer bytes only; Ghidra code/xref claims, "
                          "instruction boundaries, dynamic API resolution and IDF loading remain unproven.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pe", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--private-ghidra", type=Path, required=True)
    p.add_argument("--public-ghidra", type=Path, required=True)
    p.add_argument("--output", type=Path, help="Aggregate-only JSON, not private reference addresses")
    args = p.parse_args()
    inputs = (args.pe, args.private_ghidra, args.public_ghidra)
    if args.output and args.output.resolve() in {item.resolve() for item in inputs}:
        p.error("Output must not overwrite any private input")
    try:
        with args.pe.open("rb") as stream:
            data = stream.read(MAX_PE + 1)
        report = audit(data, args.expected_sha256,
                       limited_json(args.private_ghidra), limited_json(args.public_ghidra))
        result = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result, encoding="utf-8")
        print(result, end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        # Do not echo exception text, which could contain private paths.
        print(json.dumps({"schema": SCHEMA, "status": "FAIL", "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
