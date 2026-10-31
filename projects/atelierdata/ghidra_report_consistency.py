"""Validate private Ghidra evidence against a SHA256-gated private PE triage.

Reads metadata only; never opens or executes the original executable.
Publishes aggregate counts only, without addresses, names or file content.
A structurally valid report does NOT establish a reachable IDF decoder.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

MAX_JSON = 8 * 1024 * 1024
MAX_CANDIDATES = 20000
FLAGS = ("push_call_instruction_verified", "literal_pointer_verified",
         "ghidra_reference_to_iat", "in_ghidra_entrypoint_direct_call_graph")


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError("Missing, linked or oversized report")
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("Report too large")
    return json.loads(raw.decode("utf-8"))


def _int(value, name, upper=MAX_CANDIDATES):
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError("Invalid " + name)
    return value


def validate(triage, ghidra):
    if not isinstance(triage, dict) or not isinstance(ghidra, dict):
        raise ValueError("Expected JSON objects")
    if triage.get("schema") != "atelierdata-loadlibrary-literal-private-v1":
        raise ValueError("Unexpected triage schema")
    if ghidra.get("schema") != "atelierdata-ghidra-loadlibrary-private-v1":
        raise ValueError("Unexpected Ghidra schema")
    sha = triage.get("sha256")
    md5 = triage.get("md5")
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise ValueError("Invalid triage SHA256")
    if not isinstance(md5, str) or not re.fullmatch(r"[a-f0-9]{32}", md5):
        raise ValueError("Invalid triage MD5")
    if (ghidra.get("source_sha256") != sha
            or ghidra.get("source_md5") != md5
            or ghidra.get("ghidra_executable_md5_verified") is not True):
        raise ValueError("Mismatched original identity")
    for flag in ("target_executed", "cfg_reachability_proven", "idf_decoder_proven"):
        if ghidra.get(flag) is not False:
            raise ValueError("Unsupported Ghidra proof flag: " + flag)
    originals = triage.get("candidates")
    rows = ghidra.get("candidates")
    if (not isinstance(originals, list) or not isinstance(rows, list)
            or len(originals) > MAX_CANDIDATES or len(rows) != len(originals)
            or _int(ghidra.get("candidate_count"), "candidate count") != len(originals)):
        raise ValueError("Candidate count mismatch")
    original_by_address = {}
    for item in originals:
        if not isinstance(item, dict):
            raise ValueError("Invalid original candidate")
        address = _int(item.get("call_va"), "call VA", 0xffffffff)
        if address in original_by_address:
            raise ValueError("Duplicate original call VA")
        original_by_address[address] = item
    seen = set()
    counts = [0] * len(FLAGS)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid Ghidra candidate")
        address = _int(row.get("call_va"), "Ghidra call VA", 0xffffffff)
        if address not in original_by_address or address in seen:
            raise ValueError("Ghidra call VA missing or duplicated")
        seen.add(address)
        original = original_by_address[address]
        for index, flag in enumerate(FLAGS):
            value = row.get(flag)
            if type(value) is not bool:
                raise ValueError("Missing/invalid boolean: " + flag)
            counts[index] += value
        recognized, literal, iat, in_graph = (row[flag] for flag in FLAGS)
        if (literal and (not recognized or original.get("literal") is None)
                or iat and not recognized or in_graph and
                (not recognized or not row.get("containing_function"))):
            raise ValueError("Contradictory candidate evidence")
    fields = ("recognized_instruction_pairs", "verified_literal_pointers",
              "iat_references", "verified_candidates_in_direct_call_graph")
    for field, count in zip(fields, counts):
        if _int(ghidra.get(field), field) != count:
            raise ValueError("Inconsistent aggregate: " + field)
    roots = _int(ghidra.get("ghidra_declared_entry_roots_with_functions"), "entry roots")
    visited = _int(ghidra.get("direct_call_graph_functions_visited"),
                   "visited functions", 1000000)
    if roots > visited or type(ghidra.get("direct_call_graph_complete_within_budget")) is not bool:
        raise ValueError("Invalid direct call graph metadata")
    return {
        "schema": "atelierdata-ghidra-public-aggregate-v1",
        "source_sha256": sha,
        "candidate_count": len(rows),
        **dict(zip(fields, counts)),
        "entry_roots": roots,
        "direct_call_graph_functions_visited": visited,
        "direct_call_graph_complete_within_budget":
            ghidra["direct_call_graph_complete_within_budget"],
        "ghidra_report_consistency_checked": True,
        "ghidra_executable_md5_reported_verified": True,
        "original_executed_by_validator": False,
        "cfg_reachability_proven": False,
        "idf_decoder_proven": False,
        "limitations": "Only report consistency; Ghidra instruction and direct-edge findings are not runtime proof."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-triage", type=Path, required=True)
    parser.add_argument("--private-ghidra", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    targets = [p.resolve() for p in
               (args.private_triage, args.private_ghidra, args.public_output)]
    if len(set(targets)) != 3:
        parser.error("Input and output paths must be distinct")
    summary = validate(_read(args.private_triage), _read(args.private_ghidra))
    args.public_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("GHIDRA_REPORT_CONSISTENCY=PASS candidates=" + str(summary["candidate_count"]))


if __name__ == "__main__":
    main()
