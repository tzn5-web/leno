"""Correlate *private* Ghidra IDF-string and file-API xref reports.

Pure metadata processing: no target execution, no .IDF reads, no decoding.
Only aggregate counts are written to the public output. A function appearing
in both reports is a candidate for manual inspection, NOT a proven decoder.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MAX_REPORT = 16 * 1024 * 1024
MAX_ITEMS = 200000
_SHA = re.compile(r"[0-9a-f]{64}\Z")


_FUNCTION_ADDRESS = re.compile(
    r"(?:(?P<space>[A-Za-z][A-Za-z0-9_]*):)?(?P<value>(?:0[xX])?[0-9A-Fa-f]{1,16})\Z"
)


def _function_key(value):
    """Normalize numeric Ghidra function addresses without merging spaces.

    Ghidra may render one PE32 address as 00401000, 0x401000 or
    RAM:00401000. EXTERNAL:401000 must not match RAM:401000.
    """
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("Invalid Ghidra function address")
    match = _FUNCTION_ADDRESS.fullmatch(value)
    if not match:
        raise ValueError("Invalid Ghidra function address")
    return ((match.group("space") or "ram").casefold(),
            int(match.group("value"), 16))


def load_private(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT:
        raise ValueError("Private report missing, linked, or oversized")
    # Duplicate JSON keys can silently replace identity, coverage or reference
    # fields. Reject ambiguous private evidence rather than trusting last-wins.
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key in private Ghidra report")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object)


def _identity(report, expected_sha256):
    if not isinstance(report, dict) or report.get("source_sha256") != expected_sha256:
        raise ValueError("Ghidra report source SHA256 mismatch")
    if report.get("idf_decoder_proven") is not False:
        raise ValueError("Ghidra report must not assert IDF decoding")
    execution_flags = [report[key] for key in ("target_executed", "executed_target_binary")
                       if key in report]
    if not execution_flags or any(flag is not False for flag in execution_flags):
        raise ValueError("Ghidra report must consistently declare no target execution")


# These API families are only static xref triage categories. An xref to an
# imported symbol is not proof of a runtime-reachable call or .IDF parsing.
# Keep dynamic lookup separate: GetProcAddress alone is not file I/O.
_API_FAMILIES = {
    "file_open": frozenset(("CreateFileA", "CreateFileW")),
    "file_read": frozenset(("ReadFile",)),
    "file_position": frozenset(("SetFilePointer", "SetFilePointerEx")),
    "file_mapping": frozenset(("CreateFileMappingA", "CreateFileMappingW",
                               "MapViewOfFile")),
    "dynamic_lookup": frozenset(("GetProcAddress",)),
}
_DIRECT_IO_FAMILIES = ("file_open", "file_read", "file_position", "file_mapping")

# Match Ghidra RefType names exactly. A substring check such as
# "CALL" in type would incorrectly classify arbitrary metadata like
# "NOT_CALL" or "CALL_HINT" as a verified control-flow reference.
_FLOW_REF_TYPES = frozenset((
    "UNCONDITIONAL_CALL", "CONDITIONAL_CALL", "COMPUTED_CALL",
    "UNCONDITIONAL_JUMP", "CONDITIONAL_JUMP", "COMPUTED_JUMP",
))
_NONFLOW_REF_TYPES = frozenset((
    "DATA", "READ", "WRITE", "READ_WRITE", "PARAM", "INDIRECTION",
    "EXTERNAL_REF", "DATA_IND",
))


def _reference_flow_from_type(reference_type):
    if reference_type in _FLOW_REF_TYPES:
        return True
    if reference_type in _NONFLOW_REF_TYPES:
        return False
    return None


_IDF_CAP_FLAGS = ("block_scan_cap_reached", "keyword_match_cap_reached",
                  "keyword_xref_cap_reached", "short_memory_read")


def _idf_coverage(report):
    # Older private Ghidra reports did not record caps. Never silently treat
    # those reports as complete just because no truncation flag was emitted.
    keys = _IDF_CAP_FLAGS + ("keyword_scan_coverage_complete",)
    present = [key in report for key in keys]
    if not any(present):
        return "unknown"
    if not all(present):
        raise ValueError("Incomplete IDF coverage metadata")
    if any(type(report[key]) is not bool for key in keys):
        raise ValueError("Invalid IDF coverage flag")
    complete = not any(report[key] for key in _IDF_CAP_FLAGS)
    if report["keyword_scan_coverage_complete"] is not complete:
        raise ValueError("Contradictory IDF coverage metadata")
    return "complete" if complete else "capped"


def correlate(idf_report, api_report, expected_sha256):
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("Expected lowercase SHA256 required")
    _identity(idf_report, expected_sha256)
    _identity(api_report, expected_sha256)
    idf_coverage = _idf_coverage(idf_report)
    if api_report.get("schema") != "atelierdata-ghidra-file-api-xrefs-v1":
        raise ValueError("Unsupported API report")
    hits = idf_report.get("keyword_hits")
    api_symbols = api_report.get("api_symbols")
    if not isinstance(hits, dict) or not isinstance(api_symbols, dict):
        raise ValueError("Missing Ghidra xref collections")
    scan_truncated = api_report.get("symbol_scan_truncated", False)
    if type(scan_truncated) is not bool:
        raise ValueError("Invalid API scan truncation flag")
    truncated_symbol_refs = 0
    unknown_flow_refs = 0
    idf_functions = set()
    api_functions = set()
    api_code_functions = set()
    family_functions = {name: set() for name in _API_FAMILIES}
    family_code_functions = {name: set() for name in _API_FAMILIES}
    idf_refs = api_refs = 0
    # Unowned references cannot support a function-level intersection.
    idf_unowned_refs = api_unowned_refs = 0
    for block in hits.values():
        if not isinstance(block, dict):
            raise ValueError("Invalid IDF block")
        for key, matches in block.items():
            if not isinstance(key, str) or not isinstance(matches, list):
                raise ValueError("Invalid IDF matches")
            if not key.split(":", 1)[0].upper().endswith(".IDF"):
                continue
            for match in matches:
                if not isinstance(match, dict) or not isinstance(match.get("references_from"), list):
                    raise ValueError("Invalid IDF xref")
                for ref in match["references_from"]:
                    if not isinstance(ref, dict):
                        raise ValueError("Invalid IDF reference")
                    idf_refs += 1
                    if idf_refs > MAX_ITEMS:
                        raise ValueError("Too many IDF references")
                    entry = ref.get("function_entry")
                    if entry is not None:
                        idf_functions.add(_function_key(entry))
                    else:
                        idf_unowned_refs += 1
    for api_name, symbols in api_symbols.items():
        if not isinstance(api_name, str) or len(api_name) > 100 or not isinstance(symbols, list):
            raise ValueError("Invalid API symbol list")
        for symbol in symbols:
            if not isinstance(symbol, dict) or not isinstance(symbol.get("references"), list):
                raise ValueError("Invalid API symbol")
            refs_truncated = symbol.get("references_truncated", False)
            if type(refs_truncated) is not bool:
                raise ValueError("Invalid API reference truncation flag")
            truncated_symbol_refs += int(refs_truncated)
            for ref in symbol["references"]:
                if not isinstance(ref, dict):
                    raise ValueError("Invalid API reference")
                api_refs += 1
                if api_refs > MAX_ITEMS:
                    raise ValueError("Too many API references")
                # Validate every reference, including those without a containing
                # function. Unowned evidence must not bypass schema checks.
                flow = ref.get("reference_is_call_or_jump")
                if flow is not None and type(flow) is not bool:
                    raise ValueError("Invalid Ghidra reference flow flag")
                reference_type = ref.get("reference_type")
                if reference_type is not None and not isinstance(reference_type, str):
                    raise ValueError("Invalid Ghidra reference type")
                derived_flow = (_reference_flow_from_type(reference_type)
                                if reference_type is not None else None)
                if flow is not None and derived_flow is not None and flow is not derived_flow:
                    raise ValueError("Contradictory Ghidra flow evidence")
                if derived_flow is None:
                    unknown_flow_refs += 1
                entry = ref.get("function_entry")
                if entry is not None:
                    key = _function_key(entry)
                    api_functions.add(key)
                    # An instruction mnemonic alone is insufficient: a CALL
                    # instruction can have a DATA reference to a different
                    # operand. Count only Ghidra flow references.
                    # A Boolean emitted by a report is not independent proof
                    # of an instruction-flow xref. Only a recognized Ghidra
                    # RefType may establish that classification. In particular,
                    # NOT_CALL + true and legacy type-less + true must remain
                    # unknown rather than inflate confirmed call counts.
                    if derived_flow is None:
                        is_call_or_jump = False
                    else:
                        is_call_or_jump = derived_flow
                    if is_call_or_jump:
                        api_code_functions.add(key)
                    for family, names in _API_FAMILIES.items():
                        if api_name in names:
                            family_functions[family].add(key)
                            if is_call_or_jump:
                                family_code_functions[family].add(key)
                else:
                    api_unowned_refs += 1
    direct_functions = set().union(*(family_functions[n] for n in _DIRECT_IO_FAMILIES))
    direct_code_functions = set().union(*(family_code_functions[n] for n in _DIRECT_IO_FAMILIES))
    family_shared = {
        name: len(idf_functions & family_functions[name])
        for name in _API_FAMILIES
    }
    family_shared_code = {
        name: len(idf_functions & family_code_functions[name])
        for name in _API_FAMILIES
    }
    return {
        "schema": "atelierdata-ghidra-idf-api-correlation-v1",
        "source_sha256_claims_match": True,
        "idf_reference_count": idf_refs,
        "idf_references_without_function_owner": idf_unowned_refs,
        "idf_coverage_status": idf_coverage,
        "idf_coverage_incomplete_or_unknown": idf_coverage != "complete" or bool(idf_unowned_refs),
        "api_reference_count": api_refs,
        "api_references_without_function_owner": api_unowned_refs,
        "api_scan_or_reference_coverage_truncated": scan_truncated or bool(truncated_symbol_refs),
        "api_symbols_with_truncated_references": truncated_symbol_refs,
        "idf_referencing_functions": len(idf_functions),
        "api_referencing_functions": len(api_functions),
        "api_call_or_jump_functions": len(api_code_functions),
        "api_references_with_unknown_flow_type": unknown_flow_refs,
        "api_flow_reference_classification_incomplete_or_unknown": bool(unknown_flow_refs or api_unowned_refs),
        "shared_idf_and_api_functions": len(idf_functions & api_functions),
        "shared_idf_and_api_call_or_jump_functions": len(idf_functions & api_code_functions),
        "shared_idf_and_direct_file_io_functions": len(idf_functions & direct_functions),
        "shared_idf_and_direct_file_io_call_or_jump_functions": len(idf_functions & direct_code_functions),
        "shared_idf_and_api_family_functions": family_shared,
        "shared_idf_and_api_family_call_or_jump_functions": family_shared_code,
        "target_executed": False,
        "idf_decoder_proven": False,
        "limitations": ("Static, potentially truncated Ghidra xrefs. Older IDF reports "
                        "without explicit scan coverage have unknown completeness. "
                        "A shared function is a "
                        "triage candidate, not proof of file access or decoding. "
                        "API families are xref-only triage, not proven calls. "
                        "Flow references use Ghidra reference type, never mnemonic alone; "
                        "older reports without reference type are unclassified. "
                        "References without a containing function are counted but "
                        "cannot support function-level correlation. "
                        "GetProcAddress alone is not direct file I/O. "
                        "Dynamically resolved calls, cross-function paths and "
                        "indirect edges may be missed.")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idf-private-report", type=Path, required=True)
    parser.add_argument("--api-private-report", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    paths = (args.idf_private_report, args.api_private_report, args.public_output)
    if len({p.resolve() for p in paths}) != 3 or args.public_output.is_symlink():
        parser.error("Private input and public output paths must differ and not be links")
    summary = correlate(load_private(args.idf_private_report),
                        load_private(args.api_private_report), args.expected_sha256)
    args.public_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("GHIDRA_IDF_API_CORRELATION=PASS (metadata validation only)")


if __name__ == "__main__":
    main()
