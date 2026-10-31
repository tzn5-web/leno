"""Replay SHA256-gated PE triage and cross-check a private Ghidra report.

Read-only, static interoperability research. Requires the user-authorized
original PE and two private reports on the same machine. Does not execute
the PE, decode IDF, interact with licensing, or publish private addresses.
Only an aggregate report is written; never use public CI for original data.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from ghidra_report_consistency import _read, validate
from pe_loadlibrary_literals import MAX_PE, analyze


def replay(pe_path, expected_sha256, triage, ghidra):
    path = Path(pe_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original PE missing or symbolic link")
    if path.stat().st_size > MAX_PE:
        raise ValueError("Original PE exceeds size bound")
    with path.open("rb") as stream:
        binary = stream.read(MAX_PE + 1)
    if len(binary) > MAX_PE:
        raise ValueError("Original PE exceeds size bound")
    _, independently_rebuilt = analyze(binary, expected_sha256)
    if not isinstance(triage, dict) or triage != independently_rebuilt:
        raise ValueError("Private triage differs from independently reconstructed PE evidence")
    summary = validate(independently_rebuilt, ghidra)
    summary["pe_sha256_independently_reverified"] = True
    summary["private_triage_exactly_replayed"] = True
    summary["original_executed_by_replay"] = False
    summary["idf_decoder_proven"] = False
    return summary


def _atomic_json(destination, payload):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ghidra-aggregate-", dir=str(destination.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pe", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--private-triage", type=Path, required=True)
    parser.add_argument("--private-ghidra", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.pe, args.private_triage, args.private_ghidra, args.public_output]
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(paths):
        parser.error("Input and output paths must all differ")
    if args.public_output.is_symlink():
        parser.error("Refusing symlink output")
    summary = replay(args.pe, args.expected_sha256,
                     _read(args.private_triage), _read(args.private_ghidra))
    _atomic_json(args.public_output, summary)
    print("GHIDRA_EVIDENCE_REPLAY=PASS candidates=" + str(summary["candidate_count"]))


if __name__ == "__main__":
    main()
