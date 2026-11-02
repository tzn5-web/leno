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
from ghidra_idf_callgraph_triage import FAMILIES
from pe_api_import_trust import _trusted_windows_api_import
from pe_file_io_xrefs import MAX_PE, parse_pe32

SCHEMA = "atelierdata-ghidra-api-callsite-replay-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FLOW_TYPES = frozenset(("UNCONDITIONAL_CALL", "COMPUTED_CALL",
                         "UNCONDITIONAL_JUMP", "COMPUTED_JUMP"))


def _raw_offset(data, pe, va, need=6):
    """Return a unique, initialized, file-backed mapping for *need* bytes."""
    rva = va - pe["image_base"]
    matches = []
    for sec in pe["sections"]:
        delta = rva - sec["rva"]
        if 0 <= delta and delta + need <= min(sec["raw_size"], sec["vsize"]):
            off = sec["raw_at"] + delta
            if off + need <= len(data):
                matches.append((off, sec["executable"]))
    return matches[0] if len(matches) == 1 else None



def _candidate_function_contains_site(data, pe, function, site_va, length):
    """Reject impossible Ghidra caller attribution for a raw x86 pointer site.

    The claimed function entry and the full candidate instruction must have
    unique file-backed executable mappings in the SAME PE section, with the
    entry no later than the instruction. This is only a necessary condition:
    it does not prove the instruction belongs to the function or is reachable.
    """
    space, entry_va = function
    if space != "ram" or not 0 <= entry_va <= 0xffffffff:
        return False
    entry = _raw_offset(data, pe, entry_va, 1)
    site = _raw_offset(data, pe, site_va, length)
    if entry is None or site is None or not entry[1] or not site[1]:
        return False
    entry_rva = entry_va - pe["image_base"]
    site_rva = site_va - pe["image_base"]
    for sec in pe["sections"]:
        backed = min(sec["raw_size"], sec["vsize"])
        first = sec["rva"]
        if (sec["executable"] and first <= entry_rva <= site_rva and
                site_rva + length <= first + backed):
            return True
    return False


def _idf_functions(data, pe, report):
    """Verify literal .IDF bytes at Ghidra-reported PE VAs before using xrefs.

    This validates the literal bytes and optionally a narrow raw x86
    immediate operand at an xref source. Ghidra's association of the source
    with a function is still unverified.
    Missing/invalid addresses never contribute to shared-function evidence.
    """
    functions = set()
    direct_pointer_functions = set()
    # Keep all Ghidra-claimed functions with byte-matched pointer sites for
    # provenance counters, even when ownership is later rejected.
    claimed_pointer_functions = set()
    direct_pointer_sites = set()
    # A separate stronger tier requires Ghidra to report an actual 5-byte
    # PUSH/MOV instruction starting at the source of a DATA reference.
    # It is still Ghidra-reported evidence, not independently decoded code.
    boundary_pointer_functions = set()
    boundary_pointer_sites = set()
    # Group all claims by physical pointer site before accepting a function owner.
    # Conflicting Ghidra rows must not corroborate one another.
    pointer_claims = {}
    verified = missing = mismatched = unterminated = 0
    for block in report["keyword_hits"].values():
        for name, hits in block.items():
            if not isinstance(name, str) or ":" not in name:
                continue
            term, encoding = name.rsplit(":", 1)
            if not term.upper().endswith(".IDF") or encoding not in ("ascii", "utf16le"):
                continue
            needle = term.encode("ascii" if encoding == "ascii" else "utf-16le")
            for hit in hits:
                address = hit.get("address")
                if address is None:
                    missing += 1
                    continue
                space, va = _function_key(address)
                if space != "ram" or not 0 <= va <= 0xffffffff:
                    mismatched += 1
                    continue
                mapped = _raw_offset(data, pe, va, len(needle))
                if mapped is None or data[mapped[0]:mapped[0] + len(needle)] != needle:
                    mismatched += 1
                    continue
                # A matching prefix is not a complete .IDF filename.  In
                # particular, MODELS.IDFX and MODELS.IDF.backup must not
                # establish literal/xref evidence for MODELS.IDF.  Require a
                # file-backed NUL terminator in the same uniquely mapped PE
                # section; a virtual-only terminator is not source evidence.
                terminator = b"\x00" if encoding == "ascii" else b"\x00\x00"
                suffix = _raw_offset(data, pe, va, len(needle) + len(terminator))
                if (suffix is None or
                        data[suffix[0] + len(needle):
                             suffix[0] + len(needle) + len(terminator)] != terminator):
                    unterminated += 1
                    continue
                verified += 1
                for ref in hit["references_from"]:
                    # Missing ownership metadata is not evidence that a
                    # second, otherwise identical claim is trustworthy.
                    # Keep a tombstone for byte-matched physical sites so a
                    # malformed sibling cannot be silently discarded.
                    entry = ref.get("function_entry")
                    function = _function_key(entry) if entry is not None else None
                    if function is not None:
                        functions.add(function)
                    # Independently corroborate only the narrow x86 forms
                    # PUSH imm32 and MOV reg, imm32 whose operand equals the
                    # literal VA. Other legitimate references are omitted.
                    # These bytes are NOT independently decoded instructions.
                    source = ref.get("source_address")
                    if source is None:
                        continue
                    src_space, src_va = _function_key(source)
                    if src_space != "ram" or not 0 <= src_va <= 0xffffffff:
                        continue
                    raw = _raw_offset(data, pe, src_va, 5)
                    if raw is None or not raw[1]:
                        continue
                    offset = raw[0]
                    opcode = data[offset]
                    if (opcode == 0x68 or 0xb8 <= opcode <= 0xbf) and (
                            struct.unpack_from("<I", data, offset + 1)[0] == va):
                        pointer_claims.setdefault((src_va, va), []).append(
                            (function, ref, opcode))
    ambiguous_pointer_sites = 0
    for (src_va, va), claims in pointer_claims.items():
        # A byte-matched pointer is physical evidence even if the associated
        # Ghidra function/metadata is contradictory. Keep that count separate.
        direct_pointer_sites.add((src_va, va))
        claimed_pointer_functions.update(
            function for function, _, _ in claims if function is not None)
        signatures = set()
        for function, ref, opcode in claims:
            signatures.add((
                function, ref.get("reference_is_data"),
                ref.get("instruction_start_address"),
                ref.get("instruction_length"),
                ref.get("instruction_mnemonic")))
        if len(signatures) != 1 or claims[0][0] is None:
            ambiguous_pointer_sites += 1
            continue
        function, ref, opcode = claims[0]
        plausible_owner = _candidate_function_contains_site(
            data, pe, function, src_va, 5)
        if plausible_owner:
            direct_pointer_functions.add(function)
        expected_mnemonic = "PUSH" if opcode == 0x68 else "MOV"
        start = ref.get("instruction_start_address")
        if (ref.get("reference_is_data") is True and
                ref.get("reference_type") == "DATA" and
                start is not None and
                _function_key(start) == ("ram", src_va) and
                type(ref.get("instruction_length")) is int and
                ref["instruction_length"] == 5 and
                ref.get("instruction_mnemonic") == expected_mnemonic):
            boundary_pointer_sites.add((src_va, va))
            if plausible_owner:
                boundary_pointer_functions.add(function)
    return (functions, direct_pointer_functions, len(direct_pointer_sites),
            boundary_pointer_functions, len(boundary_pointer_sites),
            verified, missing, mismatched, claimed_pointer_functions,
            ambiguous_pointer_sites, unterminated)

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
    (idf_functions, direct_idf_functions, direct_idf_pointer_refs,
     boundary_idf_functions, boundary_idf_pointer_refs,
     idf_literals_verified, idf_literals_missing_address,
     idf_literals_mismatched, claimed_idf_pointer_functions,
     ambiguous_idf_pointer_sites, idf_literals_unterminated) = _idf_functions(
         data, pe, idf_report)
    inspected = mapped_executable = nonexec = unmapped = 0
    raw_opcode_candidates = import_matched = shared_idf_matched = 0
    direct_idf_shared_sites = 0
    boundary_idf_shared_sites = 0
    opcode_flow_conflicts = duplicate_sites = ambiguous_sites = 0
    missing_instruction_evidence = inconsistent_instruction_evidence = 0
    impossible_api_function_owners = 0
    untrusted_api_import_providers = 0
    # Aggregate by physical callsite before scoring. A source address cannot
    # become two independently corroborated calls just because a private
    # Ghidra report repeats it with different containing functions.
    sites = {}
    tainted_sites = set()
    for api_name, symbols in api_report["api_symbols"].items():
        for symbol in symbols:
            for ref in symbol["references"]:
                flow_type = ref.get("reference_type")
                if flow_type not in _FLOW_TYPES:
                    continue
                source = ref.get("source_address")
                if source is None:
                    missing_instruction_evidence += 1
                    continue
                space, address = _function_key(source)
                if space != "ram" or not 0 <= address <= 0xffffffff:
                    continue
                # A malformed second claim at the same physical address
                # invalidates a valid sibling instead of being skipped.
                if (ref.get("function_entry") is None or
                        ref.get("reference_is_call_or_jump") is not True):
                    tainted_sites.add(address)
                    continue
                start = ref.get("instruction_start_address")
                length = ref.get("instruction_length")
                mnemonic = ref.get("instruction_mnemonic")
                if start is None or length is None or mnemonic is None:
                    missing_instruction_evidence += 1
                    tainted_sites.add(address)
                    continue
                if (_function_key(start) != (space, address) or
                        type(length) is not int or length != 6 or
                        mnemonic != ("CALL" if "CALL" in flow_type else "JMP")):
                    inconsistent_instruction_evidence += 1
                    tainted_sites.add(address)
                    continue
                function = _function_key(ref["function_entry"])
                if address in sites:
                    duplicate_sites += 1
                row = sites.setdefault(address, {"api_names": set(), "functions": set(), "flow_kinds": set()})
                row["api_names"].add(api_name)
                row["functions"].add(function)
                row["flow_kinds"].add("CALL" if "CALL" in flow_type else "JUMP")

    for address, row in sites.items():
        inspected += 1
        if (address in tainted_sites or len(row["api_names"]) != 1 or
                len(row["functions"]) != 1 or len(row["flow_kinds"]) != 1):
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
        if not _candidate_function_contains_site(data, pe, function, address, 6):
            impossible_api_function_owners += 1
            continue
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
        # The name ReadFile/GetProcAddress alone does not establish a Windows
        # API: an unrelated DLL may export an identically named function.
        # KERNEL32/KERNELBASE and strictly matching API-set families are
        # allowed as declared PE import providers, not runtime proof.
        families = tuple(family for family, names in FAMILIES.items()
                         if api_name in names)
        if not families:
            if api_name.startswith("LoadLibrary"):
                families = ("dynamic_lookup",)
            elif api_name in (
                    "GetFileSize", "GetFileSizeEx", "GetFileAttributesA",
                    "GetFileAttributesW", "FindFirstFileA", "FindFirstFileW",
                    "FindNextFileA", "FindNextFileW"):
                families = ("file_read",)
        dll = imported["dll"].upper()
        if (dll not in ("KERNEL32.DLL", "KERNELBASE.DLL") and
                (not families or not _trusted_windows_api_import(dll, families))):
            untrusted_api_import_providers += 1
            continue
        import_matched += 1
        if function in idf_functions:
            shared_idf_matched += 1
        if function in direct_idf_functions:
            direct_idf_shared_sites += 1
        if function in boundary_idf_functions:
            boundary_idf_shared_sites += 1
    return {
        "schema": SCHEMA,
        "original_sha256_verified": True,
        "source_md5_matches_both_ghidra_reports": True,
        "reported_api_flow_sites_with_address_inspected": inspected,
        "idf_literal_hits_verified_against_source_pe": idf_literals_verified,
        "idf_xrefs_with_raw_push_or_mov_literal_va": direct_idf_pointer_refs,
        "idf_raw_pointer_sites_with_conflicting_ghidra_claims": ambiguous_idf_pointer_sites,
        "ghidra_claimed_idf_pointer_function_count": len(claimed_idf_pointer_functions),
        "ghidra_claimed_idf_pointer_functions_rejected_by_pe_ownership":
            len(claimed_idf_pointer_functions - direct_idf_functions),
        "matching_api_sites_in_idf_raw_pointer_functions": direct_idf_shared_sites,
        "idf_xrefs_with_ghidra_boundary_and_raw_pointer": boundary_idf_pointer_refs,
        "matching_api_sites_in_ghidra_idf_pointer_functions": boundary_idf_shared_sites,
        "idf_literal_hits_missing_address": idf_literals_missing_address,
        "idf_literal_hits_unmapped_or_mismatched": idf_literals_mismatched,
        "idf_literal_hits_without_file_backed_nul_terminator": idf_literals_unterminated,
        "unique_sites_repeated_in_report": duplicate_sites,
        "sites_with_conflicting_reported_attribution": ambiguous_sites,
        "api_callsites_with_impossible_function_ownership": impossible_api_function_owners,
        "api_sites_rejected_untrusted_import_provider": untrusted_api_import_providers,
        "references_missing_ghidra_instruction_boundary_evidence": missing_instruction_evidence,
        "references_with_inconsistent_ghidra_instruction_boundary_evidence": inconsistent_instruction_evidence,
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
                       "Ghidra-reported instruction boundaries must be explicit, 6-byte, and match xref sources; they are not independently proven. "
                       "Conflicting or malformed call claims at the same physical site are excluded. "
                       "Claimed API caller entries must precede the callsite in the same uniquely backed executable PE section; this is not function-boundary proof. "
                       "A matching API name is accepted only with a recognized declared Windows import provider; actual runtime DLL resolution is unproven. "
                       "Dynamic imports, thunks, other encodings and indirect flows are omitted. "
                       "IDF literal bytes are independently checked at reported PE VAs; raw PUSH/MOV immediate-pointer matches are narrow byte candidates. "
                       "A separate stricter counter requires Ghidra-reported DATA reference, matching instruction start, 5-byte length and PUSH/MOV mnemonic, but is not independent disassembly. " 
                       "Conflicting Ghidra function or instruction-metadata claims for the same raw IDF pointer site invalidate its function-level correlation; raw byte counts remain separate. "
                       "Pointer-source function correlation additionally requires a unique, file-backed executable mapping with the reported function entry preceding the source in the same section; this does not prove ownership. " 
                       "Other IDF string xrefs and containing functions remain Ghidra claims. "
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
