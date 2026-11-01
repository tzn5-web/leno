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
from ghidra_api_callsite_replay import (_idf_functions as replay_idf_literals,
                                        _raw_offset)
from ghidra_idf_api_correlation import load_private
from ghidra_idf_callgraph_triage import (
    FAMILIES, MAX_HOPS, _api_functions, _edges,
    _reverse_distances_to_targets, analyze, load_graph,
)
from pe_file_io_xrefs import MAX_PE, parse_pe32
from ghidra_pe_api_endpoint_evidence import pe_backed_api_endpoints



def _executable_source_addresses(binary, pe, functions):
    """Only unique, initialized executable PE mappings may be graph sources.

    A verified literal or PUSH/MOV byte candidate does not establish that
    Ghidra's attributed containing function exists at the reported address.
    This filter removes impossible/non-code function entries; it does not
    independently prove Ghidra's function boundaries or control flow.
    """
    backed = set()
    for space, value in functions:
        if space != 'ram' or not 0 <= value <= 0xffffffff:
            continue
        mapped = _raw_offset(binary, pe, value, 1)
        if mapped is not None and mapped[1]:
            backed.add(value)
    return backed


def _hop_histogram(starts, distances):
    """Address-free shortest-path counts; missing paths are never inferred absent."""
    return {str(hop): sum(distances.get(source) == hop for source in starts)
            for hop in range(MAX_HOPS + 1)}


def analyze_verified(binary, expected_sha256, idf_report, api_report, graph_report):
    """Require matching source identity and independent PE byte replay first."""
    verified = replay(binary, expected_sha256, graph_report)
    summary = analyze(idf_report, api_report, graph_report, expected_sha256)
    # Cross-check reported .IDF string addresses against *source* PE bytes.
    # This is an independent, narrower evidence tier: Ghidra function
    # attribution and instruction boundaries remain unproven by raw bytes.
    pe = parse_pe32(binary)
    (literal_functions, pointer_functions, pointer_sites,
     boundary_functions, boundary_sites, verified_literals,
     missing_addresses, mismatched_literals) = replay_idf_literals(
         binary, pe, idf_report)
    if (verified['direct_call_sites_verified'] != summary['direct_call_sites_in_graph'] or
            verified['duplicate_call_sites_ignored'] != summary['duplicate_call_sites_ignored'] or
            verified['callgraph_coverage_truncated'] != summary['callgraph_coverage_truncated']):
        raise ValueError('Ghidra triage and independent PE replay disagree')
    # The baseline callgraph histogram uses ALL Ghidra-claimed .IDF xrefs.
    # A byte-mismatched literal must not count as a corroborated source.
    # API endpoint functions remain Ghidra assertions, not independently
    # replayed file-I/O instructions; label this narrower tier explicitly.
    adjacency, _, _ = _edges(graph_report)
    endpoints = _api_functions(api_report)
    direct_targets = set().union(
        *(endpoints[family] for family in FAMILIES if family != 'dynamic_lookup'))
    direct_distances = _reverse_distances_to_targets(adjacency, direct_targets)
    dynamic_distances = _reverse_distances_to_targets(
        adjacency, endpoints['dynamic_lookup'])
    # Distinct, stricter endpoint tier: only Ghidra-declared CALL FF 15
    # sites whose actual PE bytes target a matching named static import.
    # These remain byte candidates, not independently disassembled calls.
    pe_endpoints, pe_iat_sites, pe_iat_conflicts = pe_backed_api_endpoints(
        binary, pe, api_report)
    pe_direct_targets = set().union(
        *(pe_endpoints[family] for family in FAMILIES if family != 'dynamic_lookup'))
    pe_direct_distances = _reverse_distances_to_targets(adjacency, pe_direct_targets)
    pe_dynamic_distances = _reverse_distances_to_targets(
        adjacency, pe_endpoints['dynamic_lookup'])
    literal_sources = _executable_source_addresses(binary, pe, literal_functions)
    pointer_sources = _executable_source_addresses(binary, pe, pointer_functions)
    boundary_sources = _executable_source_addresses(binary, pe, boundary_functions)
    summary.update({
        'schema': 'atelierdata-ghidra-idf-verified-triage-v1',
        'idf_report_derived_hops_include_unverified_literal_xrefs': True,
        'api_endpoint_calls_independently_replayed': False,
        'pe_iat_endpoint_byte_check_performed': True,
        'pe_iat_endpoint_callsites_correlated': pe_iat_sites,
        'pe_iat_endpoint_conflicting_ghidra_attribution': pe_iat_conflicts,
        'pe_iat_direct_file_io_endpoint_function_count': len(pe_direct_targets),
        'verified_boundary_pointer_sources_by_shortest_pe_iat_file_io_hops':
            _hop_histogram(boundary_sources, pe_direct_distances),
        'verified_boundary_pointer_sources_by_shortest_pe_iat_dynamic_lookup_hops':
            _hop_histogram(boundary_sources, pe_dynamic_distances),
        'verified_literal_source_function_count': len(literal_sources),
        'ghidra_claimed_idf_function_entries_without_executable_pe_mapping':
            len(literal_functions) - len(literal_sources),
        'ghidra_claimed_pointer_function_entries_without_executable_pe_mapping':
            len(pointer_functions) - len(pointer_sources),
        'verified_raw_pointer_source_function_count': len(pointer_sources),
        'verified_boundary_pointer_source_function_count': len(boundary_sources),
        'verified_literal_sources_by_shortest_ghidra_file_io_hops':
            _hop_histogram(literal_sources, direct_distances),
        'verified_raw_pointer_sources_by_shortest_ghidra_file_io_hops':
            _hop_histogram(pointer_sources, direct_distances),
        'verified_boundary_pointer_sources_by_shortest_ghidra_file_io_hops':
            _hop_histogram(boundary_sources, direct_distances),
        'verified_literal_sources_by_shortest_ghidra_dynamic_lookup_hops':
            _hop_histogram(literal_sources, dynamic_distances),
        'original_pe_sha256_independently_verified': True,
        'original_pe_md5_matches_private_ghidra': True,
        'all_reported_call_edges_replayed_against_original_pe': True,
        'direct_rel32_call_sites_verified': verified['direct_call_sites_verified'],
        'idf_literal_hits_verified_against_original_pe': verified_literals,
        'idf_literal_hits_missing_address': missing_addresses,
        'idf_literal_hits_unmapped_or_mismatched': mismatched_literals,
        'ghidra_claimed_idf_functions_with_verified_literal_bytes': len(literal_functions),
        'verified_literal_sources_executable_pe_backed': True,
        'ghidra_claimed_idf_functions_with_raw_pointer_candidate': len(pointer_functions),
        'idf_raw_push_or_mov_pointer_sites': pointer_sites,
        'ghidra_claimed_idf_functions_with_boundary_pointer_candidate': len(boundary_functions),
        'idf_raw_pointer_sites_with_ghidra_boundary_metadata': boundary_sites,
        'original_executed': False,
        'runtime_reachability_proven': False,
        'idf_decoder_proven': False,
        'limitations': (
            'Every reported E8 rel32 edge matches original PE bytes, but Ghidra '
            'function boundaries, IDF-string xrefs and API references remain '
            'static metadata assertions. Reported IDF literal bytes are now '
            'checked against original PE mappings, but containing functions '
            'and raw PUSH/MOV pointer candidates are not independently '
            'disassembled or shown reachable. Function entries in the stricter '
            'source tiers must map to executable PE bytes; their actual '
            'boundaries and ownership of xrefs remain Ghidra claims. '
            'The legacy IDF-source hop histogram uses unverified Ghidra xrefs; '
            'separate verified-literal/pointer tiers exclude unmatched source bytes. '
            'The additional PE-IAT endpoint tier checks exact FF 15 import '
            'bytes and Ghidra-declared six-byte CALL boundaries; it excludes '
            'dynamic resolution, delayed imports and all other call forms. '
            'Even these matching raw bytes do not independently establish '
            'instruction boundaries or reachable file operations. '
            'File-I/O API endpoint references are still Ghidra metadata, not '
            'independently replayed instructions. '
            'Static byte matches are not independently replayed dataflow. '
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
