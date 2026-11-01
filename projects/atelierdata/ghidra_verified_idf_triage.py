"""Fail-closed private PE32/Ghidra callgraph triage for authorized interoperability.

Replays every reported direct x86 call edge against original PE bytes, then
correlates Ghidra IDF-string and file-API xrefs. Only aggregate counts leave
this process; no proprietary bytes, strings, offsets, or callsites are exported.
Neither xref provenance nor runtime reachability is established by byte replay.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from ghidra_callgraph_source_replay import replay
from ghidra_idf_api_correlation import load_private
from ghidra_idf_callgraph_triage import analyze, load_graph
from pe_file_io_xrefs import MAX_PE


def analyze_verified(binary, expected_sha256, idf_report, api_report, graph_report):
    """Require matching source identity and independent PE byte replay first."""
    verified = replay(binary, expected_sha256, graph_report)
    summary = analyze(idf_report, api_report, graph_report, expected_sha256)
    if (verified['direct_call_sites_verified'] != summary['direct_call_sites_in_graph'] or
            verified['duplicate_call_sites_ignored'] != summary['duplicate_call_sites_ignored'] or
            verified['callgraph_coverage_truncated'] != summary['callgraph_coverage_truncated']):
        raise ValueError('Ghidra triage and independent PE replay disagree')
    summary.update({
        'schema': 'atelierdata-ghidra-idf-verified-triage-v1',
        'original_pe_sha256_independently_verified': True,
        'original_pe_md5_matches_private_ghidra': True,
        'all_reported_call_edges_replayed_against_original_pe': True,
        'direct_rel32_call_sites_verified': verified['direct_call_sites_verified'],
        'original_executed': False,
        'runtime_reachability_proven': False,
        'idf_decoder_proven': False,
        'limitations': (
            'Every reported E8 rel32 edge matches original PE bytes, but Ghidra '
            'function boundaries, IDF-string xrefs and API references remain '
            'static metadata assertions, not independently replayed dataflow. '
            'No runtime reachability, IDF parser, decryption or licensed data '
            'access is demonstrated. Truncated coverage and indirect calls '
            'prevent negative conclusions.'
        ),
    })
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--idf-private-report', type=Path, required=True)
    parser.add_argument('--api-private-report', type=Path, required=True)
    parser.add_argument('--callgraph-private-report', type=Path, required=True)
    parser.add_argument('--public-output', type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = (args.pe, args.idf_private_report, args.api_private_report,
              args.callgraph_private_report)
    paths = (*inputs, args.public_output)
    if any(p.is_symlink() for p in paths) or len({p.resolve() for p in paths}) != len(paths):
        parser.error('All private inputs and public output must be distinct non-symlink paths')
    if not args.pe.is_file() or args.pe.stat().st_size > MAX_PE:
        parser.error('Original PE missing or exceeds size limit')
    with args.pe.open('rb') as handle:
        binary = handle.read(MAX_PE + 1)
    if len(binary) > MAX_PE:
        parser.error('Original PE exceeds size limit')
    summary = analyze_verified(
        binary, args.expected_sha256,
        load_private(args.idf_private_report),
        load_private(args.api_private_report),
        load_graph(args.callgraph_private_report),
    )
    # Atomic replacement prevents incomplete public reports on failure.
    fd, temp = tempfile.mkstemp(prefix='.atelierdata-verified-', dir=str(args.public_output.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write('\n')
        if args.public_output.is_symlink():
            raise ValueError('Refusing linked output')
        os.replace(temp, args.public_output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print('GHIDRA_IDF_VERIFIED_TRIAGE=PASS (static original PE bytes; no IDF decoding)')


if __name__ == '__main__':
    main()
