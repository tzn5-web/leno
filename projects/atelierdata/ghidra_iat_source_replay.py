"""Independently replay PE32 IAT evidence before accepting private Ghidra reports.

The original PE is read as inert bytes, bounded and SHA256-gated. The complete
private triage is rebuilt and compared byte-for-byte in meaning (JSON objects),
then the Ghidra instruction/IAT report is checked against that replay. No
original program, DLL, or proprietary IDF data is executed or exported.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ghidra_iat_consistency import load_private, validate, write_aggregate
from pe_file_io_xrefs import MAX_PE, analyze


def replay(pe_path, expected_sha256, private_triage, private_ghidra):
    path = Path(pe_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original PE missing or symbolic link")
    if path.stat().st_size > MAX_PE:
        raise ValueError("Original PE exceeds size bound")
    with path.open("rb") as stream:
        binary = stream.read(MAX_PE + 1)
    if len(binary) > MAX_PE:
        raise ValueError("Original PE exceeds size bound")
    _, reconstructed = analyze(binary, expected_sha256)
    if not isinstance(private_triage, dict) or reconstructed != private_triage:
        raise ValueError("Private IAT triage differs from independently reconstructed PE evidence")
    summary = validate(reconstructed, private_ghidra)
    summary["pe_sha256_independently_reverified"] = True
    summary["private_iat_triage_exactly_replayed"] = True
    summary["original_executed_by_replay"] = False
    summary["idf_decoder_proven"] = False
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pe", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--private-triage", type=Path, required=True)
    parser.add_argument("--private-ghidra", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()
    paths = (args.pe, args.private_triage, args.private_ghidra, args.public_output)
    if len({p.resolve() for p in paths}) != len(paths):
        parser.error("Input and output paths must all differ")
    if args.public_output.is_symlink():
        parser.error("Refusing linked public output")
    summary = replay(args.pe, args.expected_sha256,
                     load_private(args.private_triage), load_private(args.private_ghidra))
    write_aggregate(args.public_output, summary)
    print("GHIDRA_IAT_SOURCE_REPLAY=PASS candidates=" + str(summary["candidate_count"]))


if __name__ == "__main__":
    main()
