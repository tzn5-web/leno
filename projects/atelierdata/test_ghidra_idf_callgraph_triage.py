"""Synthetic, non-proprietary direct-callgraph triage regression tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_idf_callgraph_triage import analyze, load_graph

SHA = 'a' * 64
MD5 = 'b' * 32


def fixtures():
    idf = {'source_sha256': SHA, 'source_md5': MD5,
           'executed_target_binary': False, 'idf_decoder_proven': False,
           'keyword_hits': {'.rdata': {'MODELS.IDF:ascii': [
               {'address': '00404000', 'references_from': [
                   {'function_entry': '00401000', 'source_address': '00401010'}]}]}}}
    api = {'schema': 'atelierdata-ghidra-file-api-xrefs-v1',
           'source_sha256': SHA, 'source_md5': MD5, 'target_executed': False,
           'idf_decoder_proven': False,
           'api_symbols': {
               'ReadFile': [{'references': [{'function_entry': '00403000',
                   'reference_type': 'UNCONDITIONAL_CALL', 'reference_is_call_or_jump': True}]}],
               'GetProcAddress': [{'references': [{'function_entry': '00401000',
                   'reference_type': 'UNCONDITIONAL_CALL', 'reference_is_call_or_jump': True}]}]}}
    graph = {'schema': 'atelierdata-ghidra-direct-callgraph-v1',
             'source_sha256': SHA, 'source_md5': MD5,
             'source_sha256_verified': True,
             'ghidra_import_sha256_verified': True,
             'ghidra_import_md5_verified': True,
             'target_executed': False, 'idf_decoder_proven': False,
             'coverage_truncated': False,
             'edges': [
                 {'caller': '00401000', 'callee': '00402000', 'site': '00401050',
                  'reference_type': 'UNCONDITIONAL_CALL'},
                 {'caller': '00402000', 'callee': '00403000', 'site': '00402050',
                  'reference_type': 'UNCONDITIONAL_CALL'}]}
    return idf, api, graph


class CallgraphTests(unittest.TestCase):
    def test_two_hops_and_dynamic_lookup_separate(self):
        result = analyze(*fixtures(), SHA)
        self.assertEqual(result['idf_sources_by_shortest_direct_file_io_hops']['2'], 1)
        self.assertEqual(result['idf_sources_by_shortest_api_family_hops']['file_read']['2'], 1)
        self.assertEqual(result['idf_sources_by_shortest_api_family_hops']['dynamic_lookup']['0'], 1)
        self.assertFalse(result['idf_decoder_proven'])
        self.assertNotIn('00401000', json.dumps(result))

    def test_data_reference_not_api_endpoint(self):
        idf, api, graph = fixtures()
        api['api_symbols']['ReadFile'][0]['references'][0]['reference_type'] = 'DATA'
        api['api_symbols']['ReadFile'][0]['references'][0]['reference_is_call_or_jump'] = False
        result = analyze(idf, api, graph, SHA)
        self.assertEqual(result['idf_sources_by_shortest_direct_file_io_hops']['2'], 0)

    def test_missing_call_edge_not_claimed(self):
        idf, api, graph = fixtures()
        graph['edges'].pop()
        result = analyze(idf, api, graph, SHA)
        self.assertEqual(sum(result['idf_sources_by_shortest_direct_file_io_hops'].values()), 0)

    def test_duplicate_callsite_not_double_counted(self):
        idf, api, graph = fixtures()
        graph['edges'].append(copy.deepcopy(graph['edges'][0]))
        result = analyze(idf, api, graph, SHA)
        self.assertEqual(result['direct_call_sites_in_graph'], 2)
        self.assertEqual(result['duplicate_call_sites_ignored'], 1)

    def test_conflicting_callsite_rejected(self):
        idf, api, graph = fixtures()
        duplicate = dict(graph['edges'][0], callee='00403000')
        graph['edges'].append(duplicate)
        with self.assertRaisesRegex(ValueError, 'Contradictory targets'):
            analyze(idf, api, graph, SHA)

    def test_wrong_md5_rejected(self):
        idf, api, graph = fixtures()
        graph['source_md5'] = 'c' * 32
        with self.assertRaisesRegex(ValueError, 'source MD5'):
            analyze(idf, api, graph, SHA)

    def test_unverified_program_rejected(self):
        idf, api, graph = fixtures()
        graph['ghidra_import_md5_verified'] = False
        with self.assertRaisesRegex(ValueError, 'identity not verified'):
            analyze(idf, api, graph, SHA)

    def test_non_ram_edge_rejected(self):
        idf, api, graph = fixtures()
        graph['edges'][0]['caller'] = 'EXTERNAL:00401000'
        with self.assertRaisesRegex(ValueError, 'RAM PE32'):
            analyze(idf, api, graph, SHA)

    def test_computed_edge_rejected(self):
        idf, api, graph = fixtures()
        graph['edges'][0]['reference_type'] = 'COMPUTED_CALL'
        with self.assertRaisesRegex(ValueError, 'Only direct unconditional'):
            analyze(idf, api, graph, SHA)

    def test_private_graph_loader_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'graph.json'
            source.write_text(json.dumps(fixtures()[2]), encoding='utf-8')
            self.assertEqual(load_graph(source)['schema'], 'atelierdata-ghidra-direct-callgraph-v1')
            link = Path(tmp) / 'link.json'
            try:
                link.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest('Symlink unavailable')
            with self.assertRaisesRegex(ValueError, 'linked'):
                load_graph(link)

    def test_coverage_cap_visible(self):
        idf, api, graph = fixtures()
        graph['coverage_truncated'] = True
        result = analyze(idf, api, graph, SHA)
        self.assertTrue(result['callgraph_coverage_truncated'])


if __name__ == '__main__':
    unittest.main()
