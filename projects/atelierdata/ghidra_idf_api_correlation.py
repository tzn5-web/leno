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
    return json.loads(path.read_text(encoding="utf-8"))


def _identity(report, expected_sha256):
    if not isinstance(report, dict) or report.get("source_sha256") != expected_sha256:
        raise ValueError("Ghidra report source SHA256 mismatch")
    if report.get("idf_decoder_proven") is not False:
        raise ValueError("Ghidra report must not assert IDF decoding")
    if report.get("target_executed", report.get("executed_target_binary")) is not False:
        raise ValueError("Ghidra report must declare no target execution")


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
    idf_functions = set()
    api_functions = set()
    api_code_functions = set()
    idf_refs = api_refs = 0
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
                entry = ref.get("function_entry")
                if entry is not None:
                    key = _function_key(entry)
                    api_functions.add(key)
                    if ref.get("instruction_mnemonic") in ("CALL", "JMP"):
                        api_code_functions.add(key)
    return {
        "schema": "atelierdata-ghidra-idf-api-correlation-v1",
        "source_sha256_claims_match": True,
        "idf_reference_count": idf_refs,
        "idf_coverage_status": idf_coverage,
        "idf_coverage_incomplete_or_unknown": idf_coverage != "complete",
        "api_reference_count": api_refs,
        "api_scan_or_reference_coverage_truncated": scan_truncated or bool(truncated_symbol_refs),
        "api_symbols_with_truncated_references": truncated_symbol_refs,
        "idf_referencing_functions": len(idf_functions),
        "api_referencing_functions": len(api_functions),
        "api_call_or_jump_functions": len(api_code_functions),
        "shared_idf_and_api_functions": len(idf_functions & api_functions),
        "shared_idf_and_api_call_or_jump_functions": len(idf_functions & api_code_functions),
        "target_executed": False,
        "idf_decoder_proven": False,
        "limitations": ("Static, potentially truncated Ghidra xrefs. Older IDF reports "
                        "without explicit scan coverage have unknown completeness. "
                        "A shared function is a "
                        "triage candidate, not proof of file access or decoding. "
                        "Dynamically resolved calls and indirect edges may be missed.")
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
