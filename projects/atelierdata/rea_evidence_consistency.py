"""Read-only REA PE-import evidence reconciliation for authorized interoperability.

Does not execute PE files or decode IDF. The private REA report remains local;
public output includes only counts. Optional --source-pe independently checks
SHA256 and reconciles standard imports using the existing PE32 static parser.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "atelierdata-rea-evidence-reconciliation-public-v1"
MAX_REPORT = 8 * 1024 * 1024
MAX_PE = 64 * 1024 * 1024
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
ISSUE_CODES = frozenset({"unsupported_form", "name_unreadable", "thunk_unreadable", "malformed_entry"})


def _integer(value, label, minimum=0, maximum=2**32 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid " + label)
    return value


def _digest(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("Invalid SHA256")
    return value.lower()


def _load(path: Path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT + 1)
    if len(raw) > MAX_REPORT:
        raise ValueError("Oversized REA report")
    return json.loads(raw)


def reconcile(report: dict, expected_sha256: str, source_pe: bytes | None = None) -> dict:
    expected = _digest(expected_sha256)
    if not isinstance(report, dict) or report.get("operation") != "inspect_pe_imports":
        raise ValueError("Unexpected REA operation")
    subject, norm = report.get("subject"), report.get("normalized_result")
    if not isinstance(subject, dict) or not isinstance(norm, dict):
        raise ValueError("Missing REA provenance")
    if not isinstance(subject.get("digest"), dict) or _digest(subject["digest"].get("sha256")) != expected:
        raise ValueError("Subject digest mismatch")
    artifact = norm.get("artifact")
    if not isinstance(artifact, dict) or _digest(artifact.get("sha256")) != expected:
        raise ValueError("Artifact digest mismatch")
    file_size = _integer(artifact.get("bytes"), "artifact size", 256, MAX_PE)
    if norm.get("format") != "pe32" or norm.get("machine") != 332 or norm.get("bits") != 32:
        raise ValueError("Expected x86 PE32 report")
    imports, delayed, issues, coverage = (norm.get(k) for k in
                                           ("imports", "delay_imports", "issues", "coverage"))
    if not all(isinstance(x, list) for x in (imports, delayed, issues)) or not isinstance(coverage, dict):
        raise ValueError("Malformed import evidence")
    if len(imports) > 256 or len(delayed) > 8192 or len(issues) > 100000:
        raise ValueError("Excessive evidence rows")
    symbol_count, static_names, seen_iat = 0, [], set()
    for dll in imports:
        if not isinstance(dll, dict) or not isinstance(dll.get("name"), str) or not isinstance(dll.get("functions"), list):
            raise ValueError("Malformed static import")
        static_names.append(dll["name"].lower())
        for fn in dll["functions"]:
            if not isinstance(fn, dict):
                raise ValueError("Malformed import function")
            rva = _integer(fn.get("iat_rva"), "IAT RVA")
            if rva in seen_iat:
                raise ValueError("Duplicate IAT RVA")
            seen_iat.add(rva)
            symbol_count += 1
    if len(set(static_names)) != len(static_names):
        raise ValueError("Duplicate static DLL descriptor")
    if symbol_count != _integer(coverage.get("imports"), "coverage imports", 0, 8192):
        raise ValueError("Static import count mismatch")
    counts = Counter()
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("code") not in ISSUE_CODES:
            raise ValueError("Unknown or malformed issue")
        counts[issue["code"]] += 1
    if coverage.get("status") == "complete" and issues:
        raise ValueError("Complete coverage contradicts issues")
    delay_dir = norm.get("delay_import_directory")
    if not isinstance(delay_dir, dict):
        raise ValueError("Missing delay directory")
    delay_size = _integer(delay_dir.get("size"), "delay directory size")
    seen_indices = set()
    malformed_attributes = outside_declared = unnamed = 0
    for row in delayed:
        if not isinstance(row, dict):
            raise ValueError("Malformed delay descriptor")
        index = _integer(row.get("index"), "delay index", 0, 8192)
        if index in seen_indices:
            raise ValueError("Duplicate delay descriptor index")
        seen_indices.add(index)
        attrs = _integer(row.get("attributes"), "delay attributes")
        malformed_attributes += attrs not in (0, 1)
        outside_declared += index * 32 + 32 > delay_size
        unnamed += not isinstance(row.get("name"), str) or not row.get("name")
    if source_pe is not None:
        if not isinstance(source_pe, bytes) or len(source_pe) != file_size:
            raise ValueError("Source PE size mismatch")
        if hashlib.sha256(source_pe).hexdigest() != expected:
            raise ValueError("Source PE SHA256 mismatch")
        from pe_file_io_xrefs import parse_pe32
        parsed = parse_pe32(source_pe)
        actual = {(v["dll"].lower(), v["symbol"], va - parsed["image_base"])
                  for va, v in parsed["imports"].items()}
        reported = {(dll["name"].lower(), fn.get("name") or ("#" + str(fn.get("ordinal"))), fn["iat_rva"])
                    for dll in imports for fn in dll["functions"]}
        if actual != reported:
            raise ValueError("Independent static import table differs from REA")
    return {
        "schema": SCHEMA, "source_sha256": expected,
        "source_bytes_reported": file_size,
        "rea_evidence_internal_consistency": "PASS",
        "original_pe_independently_verified": source_pe is not None,
        "static_import_dll_count": len(imports),
        "static_import_function_count": symbol_count,
        "delay_directory_declared_bytes": delay_size,
        "delay_full_descriptors_within_declared_bytes": delay_size // 32,
        "delay_trailing_bytes": delay_size % 32,
        "rea_delay_rows": len(delayed),
        "rea_delay_rows_invalid_attributes": malformed_attributes,
        "rea_delay_rows_outside_declared_directory": outside_declared,
        "rea_delay_rows_without_dll_name": unnamed,
        "rea_issues_by_code": {code: counts[code] for code in sorted(ISSUE_CODES)},
        "rea_total_issues": len(issues),
        "rea_delay_import_functions_verified": 0,
        "original_executed": False, "idf_loader_proven": False,
        "idf_decoder_proven": False,
        "limitations": "Reconciles previously produced REA JSON; not a new REA/Ghidra execution. "
                       "Without --source-pe, SHA256 is an evidence assertion, not an independent byte check. "
                       "Malformed delay rows are not verified imports, and cannot establish IDF handling.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rea-report", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--source-pe", type=Path)
    p.add_argument("--public-output", type=Path, required=True)
    args = p.parse_args()
    inputs = {args.rea_report.resolve()}
    if args.source_pe:
        inputs.add(args.source_pe.resolve())
    if args.public_output.resolve() in inputs:
        p.error("Public output must not overwrite private inputs")
    try:
        report = _load(args.rea_report)
        source = None
        if args.source_pe:
            with args.source_pe.open("rb") as stream:
                source = stream.read(MAX_PE + 1)
        result = reconcile(report, args.expected_sha256, source)
        args.public_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("REA_EVIDENCE_RECONCILIATION=PASS source_pe_verified=" + str(source is not None))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("REA_EVIDENCE_RECONCILIATION=FAIL type=" + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
