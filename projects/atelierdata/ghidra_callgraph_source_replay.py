"""Independently replay private Ghidra x86 direct-call edges against an authorized PE32.

Reads inert PE bytes only; never executes the target or parses proprietary IDF.
Only aggregate, address-free results may be written outside the private workspace.
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

from ghidra_idf_callgraph_triage import (
    EDGE_VERIFICATION, GRAPH_SCHEMA, MAX_EDGES, _address, _edges,
)
from pe_file_io_xrefs import MAX_PE, parse_pe32

_SHA = re.compile(r"[0-9a-f]{64}\Z")


def replay(binary, expected_sha256, report):
    """Fail closed on inconsistent identity, unmapped code, or wrong rel32 bytes."""
    if not isinstance(binary, bytes) or len(binary) > MAX_PE:
        raise ValueError("Expected bounded original PE bytes")
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("Expected lowercase SHA256 required")
    if hashlib.sha256(binary).hexdigest() != expected_sha256:
        raise ValueError("Original PE SHA256 mismatch")
    if not isinstance(report, dict) or report.get("schema") != GRAPH_SCHEMA:
        raise ValueError("Unsupported private Ghidra callgraph schema")
    if report.get("source_sha256") != expected_sha256 or report.get("source_md5") != hashlib.md5(binary).hexdigest():
        raise ValueError("Private Ghidra callgraph source hash mismatch")
    for flag in ("source_sha256_verified", "ghidra_import_sha256_verified", "ghidra_import_md5_verified"):
        if report.get(flag) is not True:
            raise ValueError("Ghidra identity verification missing")
    if report.get("target_executed") is not False or report.get("idf_decoder_proven") is not False:
        raise ValueError("Invalid target execution/decoder claim")
    if report.get("edge_verification") != EDGE_VERIFICATION:
        raise ValueError("Unsupported callgraph edge verification contract")
    if type(report.get("coverage_truncated")) is not bool:
        raise ValueError("Missing callgraph coverage flag")
    adjacency, unique_sites, duplicates = _edges(report)
    pe = parse_pe32(binary)
    image_base = pe["image_base"]
    sections = pe["sections"]

    def executable_offset(va, size):
        if not isinstance(va, int) or va < image_base or va + size > 0x100000000:
            raise ValueError("PE32 code address outside image")
        rva = va - image_base
        matches = []
        for sec in sections:
            delta = rva - sec["rva"]
            backed = min(sec["vsize"], sec["raw_size"])
            if sec["executable"] and delta >= 0 and delta + size <= backed:
                matches.append(sec["raw_at"] + delta)
        if len(matches) != 1:
            raise ValueError("Code address not uniquely backed by executable PE bytes")
        offset = matches[0]
        if offset + size > len(binary):
            raise ValueError("Executable code bytes truncated")
        return offset

    for edge in report["edges"]:
        site = _address(edge["site"])
        caller = _address(edge["caller"])
        callee = _address(edge["callee"])
        executable_offset(caller, 1)
        executable_offset(callee, 1)
        offset = executable_offset(site, 5)
        raw = binary[offset:offset + 5]
        if raw[0] != 0xE8:
            raise ValueError("Original PE callsite is not E8 rel32")
        displacement = struct.unpack_from("<i", raw, 1)[0]
        destination = (site + 5 + displacement) & 0xffffffff
        if destination != callee:
            raise ValueError("Original PE direct-call destination mismatch")
    return {
        "schema": "atelierdata-ghidra-callgraph-source-replay-v1",
        "original_pe_sha256_independently_verified": True,
        "original_pe_md5_matches_private_ghidra": True,
        "all_reported_call_edges_replayed_against_original_pe": True,
        "direct_call_sites_verified": unique_sites,
        "duplicate_call_sites_ignored": duplicates,
        "distinct_callers_in_graph": len(adjacency),
        "callgraph_coverage_truncated": report["coverage_truncated"],
        "original_executed": False,
        "idf_decoder_proven": False,
        "limitations": (
            "Static E8 rel32 bytes only; Ghidra function boundaries and xrefs remain "
            "Ghidra assertions. Does not establish runtime reachability, dataflow, "
            "file access, proprietary data rights, or IDF decoding. "
            "Truncated graph and indirect calls cannot support negative conclusions."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pe", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--private-callgraph", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    paths = (args.pe, args.private_callgraph, args.public_output)
    if len({p.resolve() for p in paths}) != 3 or any(p.is_symlink() for p in paths):
        parser.error("All paths must be distinct, non-symlink paths")
    if not args.pe.is_file() or args.pe.stat().st_size > MAX_PE:
        parser.error("Original PE missing or exceeds size limit")
    if not args.private_callgraph.is_file() or args.private_callgraph.stat().st_size > 64 * 1024 * 1024:
        parser.error("Private callgraph missing or exceeds size limit")
    with args.pe.open("rb") as handle:
        binary = handle.read(MAX_PE + 1)
    if len(binary) > MAX_PE:
        parser.error("Original PE exceeds size limit")
    report = json.loads(args.private_callgraph.read_text(encoding="utf-8"))
    result = replay(binary, args.expected_sha256, report)
    # Atomic public aggregate only; never write source bytes, addresses or private rows.
    destination = args.public_output
    fd, temporary = tempfile.mkstemp(prefix=".atelierdata-callgraph-", dir=str(destination.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        if destination.is_symlink():
            raise ValueError("Refusing linked public output")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("GHIDRA_CALLGRAPH_SOURCE_REPLAY=PASS (static bytes only)")


if __name__ == "__main__":
    main()
