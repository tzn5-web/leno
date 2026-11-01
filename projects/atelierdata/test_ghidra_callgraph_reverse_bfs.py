"""Synthetic graph tests: no original executables, .IDF data or private addresses."""
import random
import unittest
from collections import deque
from unittest.mock import patch

from ghidra_idf_callgraph_triage import (
    MAX_HOPS, _reverse_distances_to_targets, analyze,
)
from test_ghidra_idf_callgraph_triage import fixtures, SHA


def forward_reference(graph, source, targets):
    """Slow independent oracle: shortest directed path from one source."""
    queue = deque([(source, 0)])
    visited = {source}
    while queue:
        node, hops = queue.popleft()
        if node in targets:
            return hops
        if hops == MAX_HOPS:
            continue
        for neighbor in graph.get(node, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, hops + 1))
    return None


class ReverseCallgraphTests(unittest.TestCase):
    def test_cycle_unreachable_and_depth_cap(self):
        graph = {1: {2}, 2: {3}, 3: {4}, 4: {2}, 0: {1}, 9: {10}}
        result = _reverse_distances_to_targets(graph, {4})
        self.assertEqual({n: result.get(n) for n in (0, 1, 2, 3, 4, 9)},
                         {0: None, 1: 3, 2: 2, 3: 1, 4: 0, 9: None})
        self.assertEqual(_reverse_distances_to_targets(graph, set()), {})

    def test_matches_independent_forward_bfs_on_seeded_graphs(self):
        rng = random.Random(20261101)
        for _ in range(25):
            graph = {node: set() for node in range(60)}
            for _ in range(240):
                graph[rng.randrange(60)].add(rng.randrange(60))
            targets = set(rng.sample(range(60), 7))
            result = _reverse_distances_to_targets(graph, targets)
            for source in range(60):
                self.assertEqual(result.get(source),
                                 forward_reference(graph, source, targets),
                                 (source, targets))

    def test_multiple_targets_choose_nearest(self):
        graph = {1: {2, 5}, 2: {3}, 3: {4}, 5: {6}}
        result = _reverse_distances_to_targets(graph, {4, 6})
        self.assertEqual(result[1], 2)
        self.assertEqual(result[4], 0)
        self.assertEqual(result[6], 0)

    def test_analyze_runs_one_reverse_bfs_per_family_not_per_source(self):
        idf, api, graph = fixtures()
        refs = idf['keyword_hits']['.rdata']['MODELS.IDF:ascii'][0]['references_from']
        for i in range(150):
            source = 0x00410000 + i * 0x100
            refs.append({'function_entry': '%08x' % source,
                         'source_address': '%08x' % (source + 0x10)})
            graph['edges'].append({
                'caller': '%08x' % source, 'callee': '00402000',
                'site': '%08x' % (source + 0x20),
                'reference_type': 'UNCONDITIONAL_CALL',
                'instruction_mnemonic': 'CALL', 'instruction_length': 5,
                'direct_rel32_opcode_verified': True,
                'source_executable': True, 'target_executable': True,
            })
        original = _reverse_distances_to_targets
        with patch('ghidra_idf_callgraph_triage._reverse_distances_to_targets',
                   wraps=original) as bfs:
            result = analyze(idf, api, graph, SHA)
        self.assertEqual(bfs.call_count, 6)  # 5 API families + all direct IO
        self.assertEqual(result['idf_referencing_function_count'], 151)
        self.assertEqual(result['idf_sources_by_shortest_direct_file_io_hops']['2'], 151)
        self.assertEqual(result['direct_call_sites_in_graph'], 152)
        self.assertFalse(result['idf_decoder_proven'])


if __name__ == '__main__':
    unittest.main()
