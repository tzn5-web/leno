"""Verify that private PE IAT triage evidence is byte-for-byte reproducible.

Read-only, static PE32 analysis for authorized interoperability research.
The original PE and detailed JSON stay private. Public output contains only
aggregate counts and SHA256. This is NOT a disassembler or an IDF decoder.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pe_file_io_xrefs import MAX_PE, parse_pe32

MAX_REPORT_BYTES = 32 * 1024 * 1024
MAX_CANDIDATES = 200000
PRIVATE_SCHEMA = "atelierdata-pe-iat-private-v1"
GHIDRA_SCHEMA = "atelierdata-ghidra-iat-private-v2"


def _read_json(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("Private report exceeds size bound")
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid private JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("Private report must be an object")
    return result


def _expected_candidates(data: bytes, pe: dict) -> list[dict]:
    """Independent raw-byte rescan, including exact PE section/RVA mapping."""
    result = []
    for section in pe["sections"]:
        if not section["executable"] or not section["raw_size"]:
            continue
        raw = data[section["raw_at"]:section["raw_at"] + section["raw_size"]]
        for marker, kind in ((b"\xff\x15", "call"), (b"\xff\x25", "jump")):
            at = raw.find(marker)
            while at >= 0:
                if at + 6 <= len(raw):
                    operand = struct.unpack_from("<I", raw, at + 2)[0]
                    imp = pe["imports"].get(operand)
                    if imp is not None:
                        instruction_va = pe["image_base"] + section["rva"] + at
                        if instruction_va > 0xffffffff:
                            raise ValueError("Candidate address exceeds PE32 range")
                        result.append({
                            "section": section["name"],
                            "file_offset": section["raw_at"] + at,
                            "instruction_va": instruction_va,
                            "imported_dll": imp["dll"],
                            "symbol": imp["symbol"],
                            "kind": kind,
                            "iat_va": operand,
                        })
                        if len(result) > MAX_CANDIDATES:
                            raise ValueError("Too many IAT candidates")
                at = raw.find(marker, at + 1)
    return sorted(result, key=lambda row: (row["file_offset"], row["kind"]))


def verify_evidence(data: bytes, report: dict, expected_sha256: str,
                    ghidra: dict | None = None) -> dict:
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or
            any(ch not in "0123456789abcdefABCDEF" for ch in expected_sha256)):
        raise ValueError("Expected SHA256 must be 64 hexadecimal characters")
    if len(data) > MAX_PE:
        raise ValueError("PE exceeds size bound")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("Original PE SHA256 mismatch")
    if report.get("schema") != PRIVATE_SCHEMA or report.get("sha256") != digest:
        raise ValueError("Private IAT report schema or SHA256 mismatch")
    rows = report.get("candidates")
    if not isinstance(rows, list) or len(rows) > MAX_CANDIDATES:
        raise ValueError("Invalid candidate list")
    pe = parse_pe32(data)
    expected = _expected_candidates(data, pe)
    if len(rows) != len(expected):
        raise ValueError("Candidate count differs from independent byte rescan")
    fields = ("section", "file_offset", "instruction_va", "imported_dll",
              "symbol", "kind", "iat_va")
    for index, (actual, wanted) in enumerate(zip(rows, expected)):
        if not isinstance(actual, dict) or any(actual.get(k) != wanted[k] for k in fields):
            raise ValueError(f"Candidate {index} disagrees with original PE bytes/imports")
        for key in ("file_offset", "instruction_va", "iat_va"):
            if type(actual[key]) is not int:
                raise ValueError(f"Candidate {index} has noninteger {key}")
    kinds = Counter(row["kind"] for row in expected)
    public = {
        "schema": "atelierdata-pe-iat-evidence-verified-v1",
        "original_sha256": digest,
        "candidate_count": len(expected),
        "call_candidate_count": kinds["call"],
        "jump_candidate_count": kinds["jump"],
        "executable_section_count": sum(bool(s["executable"] and s["raw_size"])
                                        for s in pe["sections"]),
        "candidate_report_matches_independent_rescan": True,
        "target_executed": False,
        "idf_decoder_proven": False,
        "limitations": "Raw byte patterns, not validated instructions or runtime calls.",
    }
    if ghidra is not None:
        if (ghidra.get("schema") != GHIDRA_SCHEMA or
                ghidra.get("original_sha256_verified") != digest or
                ghidra.get("ghidra_program_md5_verified") is not True or
                ghidra.get("candidate_count") != len(expected)):
            raise ValueError("Ghidra private report identity or count mismatch")
        checks = ghidra.get("candidates")
        if not isinstance(checks, list) or len(checks) != len(expected):
            raise ValueError("Ghidra candidate list mismatch")
        recognized = referenced = 0
        for index, (check, candidate) in enumerate(zip(checks, rows)):
            if not isinstance(check, dict) or any(
                check.get(k) != candidate[k]
                for k in ("instruction_va", "iat_va", "symbol", "kind")
            ):
                raise ValueError(f"Ghidra candidate {index} identity mismatch")
            if type(check.get("instruction_opcode_operand_verified")) is not bool or (
                type(check.get("ghidra_reference_to_iat")) is not bool
            ):
                raise ValueError("Ghidra verdict fields must be boolean")
            valid = check["instruction_opcode_operand_verified"]
            ref = check["ghidra_reference_to_iat"]
            if ref and not valid:
                raise ValueError("Ghidra IAT reference without verified instruction")
            recognized += valid
            referenced += ref
        if (ghidra.get("opcode_operand_verified") != recognized or
                ghidra.get("ghidra_references_to_iat") != referenced):
            raise ValueError("Ghidra aggregate counts disagree with detail")
        public["ghidra_report_claimed_verified_instructions"] = recognized
        public["ghidra_report_claimed_iat_references"] = referenced
        public["ghidra_report_identity_consistent"] = True
        public["ghidra_caveat"] = (
            "Internal report consistency only; independent Ghidra execution "
            "and project provenance are not established by this validator."
        )
    return public


def run(pe_path, expected_sha256, private_report_path, public_output_path,
        ghidra_private_path=None) -> dict:
    pe_path = Path(pe_path)
    private_report_path = Path(private_report_path)
    public_output_path = Path(public_output_path)
    inputs = [pe_path, private_report_path]
    if ghidra_private_path is not None:
        inputs.append(Path(ghidra_private_path))
    if public_output_path.resolve() in {p.resolve() for p in inputs}:
        raise ValueError("Public output must differ from every input")
    with pe_path.open("rb") as stream:
        data = stream.read(MAX_PE + 1)
    report = _read_json(private_report_path)
    ghidra = _read_json(Path(ghidra_private_path)) if ghidra_private_path else None
    result = verify_evidence(data, report, expected_sha256, ghidra)
    public_output_path.parent.mkdir(parents=True, exist_ok=True)
    public_output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pe", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--private-iat", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-ghidra", type=Path)
    args = parser.parse_args()
    result = run(args.pe, args.expected_sha256, args.private_iat,
                 args.public_output, args.private_ghidra)
    print("IAT_EVIDENCE_VERIFY=PASS candidates=" + str(result["candidate_count"]))


if __name__ == "__main__":
    main()
