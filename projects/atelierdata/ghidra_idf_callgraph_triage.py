"""Aggregate private Ghidra direct-call graph evidence for .IDF interoperability triage.

No target execution, data extraction or decoding. All addresses remain in
private inputs; public JSON contains only counts. A Ghidra edge is a static
hypothesis, not proof that a call executes or reads a particular file.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, deque
from pathlib import Path

from ghidra_idf_api_correlation import _function_key, correlate, load_private

SCHEMA = 'atelierdata-ghidra-idf-direct-callgraph-triage-v1'
GRAPH_SCHEMA = 'atelierdata-ghidra-direct-callgraph-v1'
SHA = re.compile(r'[0-9a-f]{64}\Z')
MD5 = re.compile(r'[0-9a-f]{32}\Z')
MAX_EDGES = 200000
MAX_FUNCTIONS = 100000
MAX_HOPS = 3
FAMILIES = {
    'file_open': frozenset(('CreateFileA', 'CreateFileW')),
    'file_read': frozenset(('ReadFile',)),
    'file_position': frozenset(('SetFilePointer', 'SetFilePointerEx')),
    'file_mapping': frozenset(('CreateFileMappingA', 'CreateFileMappingW', 'MapViewOfFile')),
    'dynamic_lookup': frozenset(('GetProcAddress',)),
}


def _address(value):
    space, number = _function_key(value)
    if space != 'ram' or not 0 <= number <= 0xffffffff:
        raise ValueError('Call graph requires RAM PE32 addresses')
    return number


def _validate_identity(idf, api, graph, sha):
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError('Expected lowercase SHA256 required')
    correlate(idf, api, sha)  # validates both xref report identities and coverage
    if not isinstance(graph, dict) or graph.get('schema') != GRAPH_SCHEMA:
        raise ValueError('Unsupported Ghidra call graph schema')
    if graph.get('source_sha256') != sha or graph.get('source_sha256_verified') is not True:
        raise ValueError('Call graph source SHA256 mismatch or unverified')
    md5 = graph.get('source_md5')
    if not isinstance(md5, str) or not MD5.fullmatch(md5):
        raise ValueError('Call graph source MD5 missing')
    if idf.get('source_md5') != md5 or api.get('source_md5') != md5:
        raise ValueError('Call graph and xref reports disagree on source MD5')
    if graph.get('ghidra_import_sha256_verified') is not True or graph.get('ghidra_import_md5_verified') is not True:
        raise ValueError('Ghidra imported program identity not verified')
    if graph.get('target_executed') is not False or graph.get('idf_decoder_proven') is not False:
        raise ValueError('Call graph must declare no execution or decoding')
    if type(graph.get('coverage_truncated')) is not bool:
        raise ValueError('Missing call graph coverage flag')


def _idf_functions(report):
    functions = set()
    for block in report['keyword_hits'].values():
        for name, hits in block.items():
            if not isinstance(name, str) or ':' not in name or not name.rsplit(':', 1)[0].upper().endswith('.IDF'):
                continue
            for hit in hits:
                for ref in hit['references_from']:
                    if ref.get('function_entry') is not None:
                        functions.add(_address(ref['function_entry']))
    if len(functions) > MAX_FUNCTIONS:
        raise ValueError('Too many IDF referencing functions')
    return functions


def _api_functions(report):
    functions = {family: set() for family in FAMILIES}
    for api_name, symbols in report['api_symbols'].items():
        families = [family for family, names in FAMILIES.items() if api_name in names]
        if not families:
            continue
        for symbol in symbols:
            for ref in symbol['references']:
                if ref.get('function_entry') is None:
                    continue
                # A DATA xref or unknown legacy flow is not a proven API call.
                if ref.get('reference_is_call_or_jump') is not True:
                    continue
                if ref.get('reference_type') not in ('UNCONDITIONAL_CALL', 'COMPUTED_CALL'):
                    continue
                fn = _address(ref['function_entry'])
                for family in families:
                    functions[family].add(fn)
    return functions


def _edges(graph):
    entries = graph.get('edges')
    if not isinstance(entries, list) or len(entries) > MAX_EDGES:
        raise ValueError('Invalid or excessive Ghidra call edges')
    adjacency = {}
    by_site = {}
    duplicates = 0
    for edge in entries:
        if not isinstance(edge, dict) or edge.get('reference_type') != 'UNCONDITIONAL_CALL':
            raise ValueError('Only direct unconditional Ghidra call references accepted')
        caller, callee, site = (_address(edge[k]) for k in ('caller', 'callee', 'site'))
        signature = (caller, callee)
        if site in by_site:
            if by_site[site] != signature:
                raise ValueError('Contradictory targets for one callsite')
            duplicates += 1
            continue
        by_site[site] = signature
        if caller != callee:
            adjacency.setdefault(caller, set()).add(callee)
    if len({x for edge in adjacency.items() for x in (edge[0], *edge[1])}) > MAX_FUNCTIONS:
        raise ValueError('Too many call graph functions')
    return adjacency, len(by_site), duplicates


def _shortest_hops(source, graph):
    distances = {source: 0}
    queue = deque((source,))
    while queue:
        current = queue.popleft()
        if distances[current] >= MAX_HOPS:
            continue
        for neighbor in graph.get(current, ()):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


def analyze(idf_report, api_report, graph_report, expected_sha256):
    _validate_identity(idf_report, api_report, graph_report, expected_sha256)
    baseline = correlate(idf_report, api_report, expected_sha256)
    starts = _idf_functions(idf_report)
    endpoints = _api_functions(api_report)
    adjacency, unique_sites, duplicates = _edges(graph_report)
    families = {name: Counter() for name in FAMILIES}
    any_direct = Counter()
    direct_families = tuple(k for k in FAMILIES if k != 'dynamic_lookup')
    direct_targets = set().union(*(endpoints[k] for k in direct_families))
    for source in starts:
        distances = _shortest_hops(source, adjacency)
        for family, targets in endpoints.items():
            hops = [distances[t] for t in targets if t in distances]
            if hops:
                families[family][min(hops)] += 1
        hops = [distances[t] for t in direct_targets if t in distances]
        if hops:
            any_direct[min(hops)] += 1
    return {
        'schema': SCHEMA,
        'original_sha256_claims_match': True,
        'original_md5_claims_match': True,
        'idf_referencing_function_count': len(starts),
        'direct_call_sites_in_graph': unique_sites,
        'duplicate_call_sites_ignored': duplicates,
        'distinct_callers_in_graph': len(adjacency),
        'idf_sources_by_shortest_direct_file_io_hops': {str(i): any_direct[i] for i in range(MAX_HOPS + 1)},
        'idf_sources_by_shortest_api_family_hops': {
            family: {str(i): families[family][i] for i in range(MAX_HOPS + 1)}
            for family in FAMILIES
        },
        'maximum_call_hops': MAX_HOPS,
        'callgraph_coverage_truncated': graph_report['coverage_truncated'],
        'idf_coverage_status': baseline['idf_coverage_status'],
        'api_coverage_truncated': baseline['api_scan_or_reference_coverage_truncated'],
        'original_executed': False,
        'runtime_reachability_proven': False,
        'idf_decoder_proven': False,
        'limitations': ('Static Ghidra-reported direct unconditional call edges only; paths do not establish runtime reachability, '
                        'file contents, dataflow, parsing, or a decoder. API endpoints require explicit call-reference metadata. '
                        'Computed/indirect calls and paths longer than three edges are omitted. '
                        'Missing edges and capped scans prevent negative conclusions.'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--idf-private-report', type=Path, required=True)
    parser.add_argument('--api-private-report', type=Path, required=True)
    parser.add_argument('--callgraph-private-report', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--public-output', type=Path, required=True)
    args = parser.parse_args()
    paths = (args.idf_private_report, args.api_private_report, args.callgraph_private_report, args.public_output)
    if len({p.resolve() for p in paths}) != 4 or any(p.is_symlink() for p in paths):
        parser.error('Inputs and output must be distinct non-symlink paths')
    result = analyze(*(load_private(p) for p in paths[:3]), args.expected_sha256)
    args.public_output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('GHIDRA_IDF_CALLGRAPH_TRIAGE=PASS (static metadata only)')


if __name__ == '__main__':
    main()
