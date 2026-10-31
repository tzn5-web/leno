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


def correlate(idf_report, api_report, expected_sha256):
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("Expected lowercase SHA256 required")
    _identity(idf_report, expected_sha256)
    _identity(api_report, expected_sha256)
    if api_report.get("schema") != "atelierdata-ghidra-file-api-xrefs-v1":
        raise ValueError("Unsupported API report")
    hits = idf_report.get("keyword_hits")
    api_symbols = api_report.get("api_symbols")
    if not isinstance(hits, dict) or not isinstance(api_symbols, dict):
        raise ValueError("Missing Ghidra xref collections")
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
                        if not isinstance(entry, str) or len(entry) > 80:
                            raise ValueError("Invalid IDF function address")
                        idf_functions.add(entry)
    for api_name, symbols in api_symbols.items():
        if not isinstance(api_name, str) or len(api_name) > 100 or not isinstance(symbols, list):
            raise ValueError("Invalid API symbol list")
        for symbol in symbols:
            if not isinstance(symbol, dict) or not isinstance(symbol.get("references"), list):
                raise ValueError("Invalid API symbol")
            for ref in symbol["references"]:
                if not isinstance(ref, dict):
                    raise ValueError("Invalid API reference")
                api_refs += 1
                if api_refs > MAX_ITEMS:
                    raise ValueError("Too many API references")
                entry = ref.get("function_entry")
                if entry is not None:
                    if not isinstance(entry, str) or len(entry) > 80:
                        raise ValueError("Invalid API function address")
                    api_functions.add(entry)
                    if ref.get("instruction_mnemonic") in ("CALL", "JMP"):
                        api_code_functions.add(entry)
    return {
        "schema": "atelierdata-ghidra-idf-api-correlation-v1",
        "source_sha256_claims_match": True,
        "idf_reference_count": idf_refs,
        "api_reference_count": api_refs,
        "idf_referencing_functions": len(idf_functions),
        "api_referencing_functions": len(api_functions),
        "api_call_or_jump_functions": len(api_code_functions),
        "shared_idf_and_api_functions": len(idf_functions & api_functions),
        "shared_idf_and_api_call_or_jump_functions": len(idf_functions & api_code_functions),
        "target_executed": False,
        "idf_decoder_proven": False,
        "limitations": ("Static, incomplete Ghidra xrefs. A shared function is a "
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
