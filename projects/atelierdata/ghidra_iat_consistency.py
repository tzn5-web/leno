"""Check private Ghidra IAT evidence against SHA256-gated PE triage.

Static report consistency only. Input contains private callsite addresses and
symbols; output contains counts only. Neither the PE nor its DLLs are executed.
A passing check does NOT establish a reachable IDF loader or decoder.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

MAX_REPORT = 16 * 1024 * 1024
MAX_ROWS = 200000


def load_private(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT:
        raise ValueError("Missing, linked or oversized private report")
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT + 1)
    if len(raw) > MAX_REPORT:
        raise ValueError("Private report too large")
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Private report must be an object")
    return result


def integer(value, label, maximum=0xffffffff):
    if type(value) is not int or value < 0 or value > maximum:
        raise ValueError("Invalid " + label)
    return value


def validate(triage, ghidra):
    if not isinstance(triage, dict) or not isinstance(ghidra, dict):
        raise ValueError("Expected JSON objects")
    if triage.get("schema") != "atelierdata-pe-iat-private-v1":
        raise ValueError("Unexpected PE triage schema")
    if ghidra.get("schema") != "atelierdata-ghidra-iat-instruction-check-v1":
        raise ValueError("Unexpected Ghidra report schema")
    sha, md5 = triage.get("sha256"), triage.get("md5")
    if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise ValueError("Invalid private SHA256")
    if not isinstance(md5, str) or re.fullmatch(r"[0-9a-f]{32}", md5) is None:
        raise ValueError("Invalid private MD5")
    if (ghidra.get("source_sha256") != sha or ghidra.get("source_md5") != md5
            or ghidra.get("ghidra_executable_md5_verified") is not True):
        raise ValueError("Imported executable identity mismatch")
    if ghidra.get("target_executed") is not False or ghidra.get("idf_decoder_proven") is not False:
        raise ValueError("Unsupported execution or decoder assertion")
    originals, rows = triage.get("candidates"), ghidra.get("candidates")
    if (not isinstance(originals, list) or not isinstance(rows, list)
            or len(originals) > MAX_ROWS or len(rows) != len(originals)
            or integer(ghidra.get("candidate_count"), "candidate count", MAX_ROWS) != len(rows)):
        raise ValueError("Candidate count mismatch")
    expected = {}
    for row in originals:
        if not isinstance(row, dict):
            raise ValueError("Invalid triage row")
        va = integer(row.get("instruction_va"), "triage VA")
        integer(row.get("iat_va"), "triage IAT")
        if va in expected or row.get("kind") not in ("call", "jump") or not isinstance(row.get("symbol"), str):
            raise ValueError("Duplicate or invalid triage candidate")
        expected[va] = row
    recognized = 0
    referenced = 0
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid Ghidra row")
        va = integer(row.get("instruction_va"), "Ghidra VA")
        if va not in expected or va in seen:
            raise ValueError("Unexpected or duplicate Ghidra VA")
        seen.add(va)
        original = expected[va]
        for field in ("symbol", "kind", "iat_va"):
            if row.get(field) != original[field] or type(row.get(field)) is not type(original[field]):
                raise ValueError("Candidate identity mismatch: " + field)
        for field in ("in_memory", "recognized_instruction", "reference_to_expected_iat"):
            if type(row.get(field)) is not bool:
                raise ValueError("Invalid Boolean: " + field)
        count = integer(row.get("references_from_instruction"), "IAT references", 100000)
        recognized_row = row["recognized_instruction"]
        reference = row["reference_to_expected_iat"]
        if (recognized_row and not row["in_memory"]) or (reference != (count > 0)) or (reference and not recognized_row):
            raise ValueError("Contradictory Ghidra evidence")
        if recognized_row and row.get("mnemonic", "").upper() != original["kind"].upper().replace("JUMP", "JMP"):
            raise ValueError("Instruction mnemonic mismatch")
        recognized += int(recognized_row)
        referenced += int(reference)
    if (integer(ghidra.get("recognized_instruction_count"), "recognized count", MAX_ROWS) != recognized
            or integer(ghidra.get("instructions_with_references"), "referenced count", MAX_ROWS) != referenced
            or integer(ghidra.get("references_to_expected_iat"), "expected IAT count", MAX_ROWS) != referenced):
        raise ValueError("Aggregate count mismatch")
    return {
        "schema": "atelierdata-ghidra-iat-public-aggregate-v1",
        "source_sha256": sha,
        "candidate_count": len(rows),
        "recognized_instruction_count": recognized,
        "references_to_expected_iat": referenced,
        "ghidra_import_md5_checked": True,
        "private_report_consistency_checked": True,
        "original_executed_by_validator": False,
        "idf_decoder_proven": False,
        "limitations": "Ghidra instruction and IAT xrefs are static evidence, not proof of a reachable IDF decoder."
    }


def write_aggregate(path, payload):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing linked output")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".iat-summary-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(payload, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-triage", type=Path, required=True)
    parser.add_argument("--private-ghidra", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    paths = [p.resolve() for p in (args.private_triage, args.private_ghidra, args.public_output)]
    if len(set(paths)) != 3:
        parser.error("Input and output paths must differ")
    summary = validate(load_private(args.private_triage), load_private(args.private_ghidra))
    write_aggregate(args.public_output, summary)
    print("GHIDRA_IAT_CONSISTENCY=PASS candidates=" + str(summary["candidate_count"]))


if __name__ == "__main__":
    main()
