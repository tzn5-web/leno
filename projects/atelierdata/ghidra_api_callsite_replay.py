"""Independently replay Ghidra file-API xrefs against authorized PE32 bytes.

A site is corroborated only if the exact executable raw-file address contains
FF 15 / FF 25 targeting a PE import whose name matches the reported API.
No target code is executed. Output is aggregate-only. Raw byte patterns are
NOT verified instruction boundaries, runtime calls, IDF loaders or decoders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import tempfile
from pathlib import Path

from ghidra_idf_api_correlation import _function_key, correlate, load_private
from pe_file_io_xrefs import MAX_PE, parse_pe32

SCHEMA = "atelierdata-ghidra-api-callsite-replay-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FLOW_TYPES = frozenset(("UNCONDITIONAL_CALL", "CONDITIONAL_CALL", "COMPUTED_CALL",
                         "UNCONDITIONAL_JUMP", "CONDITIONAL_JUMP", "COMPUTED_JUMP"))


def _raw_offset(data, pe, va):
    """Return a unique six-byte file-backed mapping, or None."""
    rva = va - pe["image_base"]
    matches = []
    for sec in pe["sections"]:
        delta = rva - sec["rva"]
        if 0 <= delta and delta + 6 <= min(sec["raw_size"], sec["vsize"]):
            off = sec["raw_at"] + delta
            if off + 6 <= len(data):
                matches.append((off, sec["executable"]))
    return matches[0] if len(matches) == 1 else None


def _idf_functions(report):
    functions = set()
    for block in report["keyword_hits"].values():
        for name, hits in block.items():
            if name.split(":", 1)[0].upper().endswith(".IDF"):
                for hit in hits:
                    for ref in hit["references_from"]:
                        if ref.get("function_entry") is not None:
                            functions.add(_function_key(ref["function_entry"]))
    return functions


def replay(data: bytes, expected_sha256: str, idf_report: dict, api_report: dict) -> dict:
    """Corroborate narrow raw IAT patterns without emitting private addresses."""
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("Expected lowercase SHA256 required")
    if len(data) > MAX_PE or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Original PE SHA256 mismatch or size limit exceeded")
    baseline = correlate(idf_report, api_report, expected_sha256)
    if (api_report.get("ghidra_program_sha256_verified") is not True or
            api_report.get("ghidra_program_md5_verified") is not True or
            idf_report.get("ghidra_import_sha256_verified") is not True):
        raise ValueError("Missing Ghidra imported-program identity flags")
    source_md5 = hashlib.md5(data).hexdigest()
    if (idf_report.get("source_md5") != source_md5 or
            api_report.get("source_md5") != source_md5):
        raise ValueError("Ghidra report source MD5 mismatch")
    pe = parse_pe32(data)
    idf_functions = _idf_functions(idf_report)
    inspected = mapped_executable = nonexec = unmapped = 0
    raw_opcode_candidates = import_matched = shared_idf_matched = 0
    opcode_flow_conflicts = duplicate_sites = ambiguous_sites = 0
    # Aggregate by physical callsite before scoring. A source address cannot
    # become two independently corroborated calls just because a private
    # Ghidra report repeats it with different containing functions.
    sites = {}
    for api_name, symbols in api_report["api_symbols"].items():
        for symbol in symbols:
            for ref in symbol["references"]:
                if ref.get("function_entry") is None:
                    continue
                flow_type = ref.get("reference_type")
                if flow_type not in _FLOW_TYPES:
                    continue
                if ref.get("reference_is_call_or_jump", True) is not True:
                    continue
                source = ref.get("source_address")
                if source is None:
                    continue
                space, address = _function_key(source)
                if space != "ram" or not 0 <= address <= 0xffffffff:
                    continue
                function = _function_key(ref["function_entry"])
                site = address
                if site in sites:
                    duplicate_sites += 1
                row = sites.setdefault(site, {"api_names": set(), "functions": set(), "flow_kinds": set()})
                row["api_names"].add(api_name)
                row["functions"].add(function)
                row["flow_kinds"].add("CALL" if "CALL" in flow_type else "JUMP")

    for address, row in sites.items():
        inspected += 1
        if len(row["api_names"]) != 1 or len(row["functions"]) != 1 or len(row["flow_kinds"]) != 1:
            # Contradictory report attribution is not evidence. This also
            # makes the result independent of private JSON reference order.
            ambiguous_sites += 1
            continue
        api_name = next(iter(row["api_names"]))
        function = next(iter(row["functions"]))
        reported_kind = next(iter(row["flow_kinds"]))
        mapped = _raw_offset(data, pe, address)
        if mapped is None:
            unmapped += 1
            continue
        off, executable = mapped
        if not executable:
            nonexec += 1
            continue
        mapped_executable += 1
        if data[off] != 0xff or data[off + 1] not in (0x15, 0x25):
            continue
        raw_opcode_candidates += 1
        kind = "CALL" if data[off + 1] == 0x15 else "JUMP"
        if kind != reported_kind:
            opcode_flow_conflicts += 1
            continue
        target = struct.unpack_from("<I", data, off + 2)[0]
        imported = pe["imports"].get(target)
        if imported is None or imported["symbol"] != api_name:
            continue
        import_matched += 1
        if function in idf_functions:
            shared_idf_matched += 1
    return {
        "schema": SCHEMA,
        "original_sha256_verified": True,
        "source_md5_matches_both_ghidra_reports": True,
        "reported_api_flow_sites_with_address_inspected": inspected,
        "unique_sites_repeated_in_report": duplicate_sites,
        "sites_with_conflicting_reported_attribution": ambiguous_sites,
        "sites_in_executable_raw_sections": mapped_executable,
        "sites_in_nonexecutable_raw_sections": nonexec,
        "sites_without_unique_raw_mapping": unmapped,
        "raw_ff15_ff25_opcode_candidates": raw_opcode_candidates,
        "opcode_vs_ghidra_flow_type_conflicts": opcode_flow_conflicts,
        "raw_indirect_import_sites_with_matching_api_name": import_matched,
        "matching_api_sites_in_idf_string_referencing_functions": shared_idf_matched,
        "idf_report_coverage_status": baseline["idf_coverage_status"],
        "api_report_truncated": baseline["api_scan_or_reference_coverage_truncated"],
        "original_executed": False,
        "instruction_boundaries_independently_verified": False,
        "runtime_reachability_proven": False,
        "idf_decoder_proven": False,
        "limitations": "Raw FF15/FF25 import-table corroboration only. Byte patterns can be data; "
                       "Ghidra xrefs and function boundaries are not independently proven. "
                       "Conflicting API names, functions or flow types for one physical site are excluded. "
                       "Dynamic imports, thunks, other encodings and indirect flows are omitted. "
                       "No evidence of an IDF decoder or licensed data access."
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pe", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--idf-private-report", type=Path, required=True)
    p.add_argument("--api-private-report", type=Path, required=True)
    p.add_argument("--public-output", type=Path, required=True)
    a = p.parse_args()
    inputs = (a.pe, a.idf_private_report, a.api_private_report)
    if any(path.is_symlink() or not path.is_file() for path in inputs):
        p.error("Private input missing or symbolic link")
    if a.public_output.is_symlink() or a.public_output.resolve() in {path.resolve() for path in inputs}:
        p.error("Public output aliases private input or is a link")
    with a.pe.open("rb") as stream:
        data = stream.read(MAX_PE + 1)
    summary = replay(data, a.expected_sha256, load_private(a.idf_private_report),
                     load_private(a.api_private_report))
    a.public_output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".atelierdata-", suffix=".json", dir=a.public_output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(summary, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(temp_path, a.public_output)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    print("GHIDRA_API_CALLSITE_REPLAY=PASS (static aggregate only)")


if __name__ == "__main__":
    main()
