"""Synthetic-only tests for private PE-backed Ghidra/IDF triage integration."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_verified_idf_triage import analyze_verified, main
from test_ghidra_callgraph_source_replay import fixture as pe_fixture
from test_ghidra_idf_callgraph_triage import fixtures as xref_fixtures


def fixture():
    binary, sha, graph = pe_fixture()
    idf, api, _ = xref_fixtures()
    md5 = hashlib.md5(binary).hexdigest()
    for report in (idf, api):
        report['source_sha256'] = sha
        report['source_md5'] = md5
    api['api_symbols']['ReadFile'][0]['references'][0]['function_entry'] = '00401060'
    return binary, sha, idf, api, graph


class VerifiedTriageTests(unittest.TestCase):
    def test_one_hop_replayed_and_aggregated(self):
        binary, sha, idf, api, graph = fixture()
        report = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(report['idf_sources_by_shortest_direct_file_io_hops']['1'], 1)
        self.assertEqual(report['direct_rel32_call_sites_verified'], 1)
        self.assertTrue(report['all_reported_call_edges_replayed_against_original_pe'])
        self.assertFalse(report['runtime_reachability_proven'])
        self.assertFalse(report['idf_decoder_proven'])
        self.assertNotIn('004010', json.dumps(report))

    def test_forged_call_destination_fails(self):
        binary, sha, idf, api, graph = fixture()
        graph['edges'][0]['callee'] = '00401061'
        with self.assertRaisesRegex(ValueError, 'destination mismatch'):
            analyze_verified(binary, sha, idf, api, graph)

    def test_tampered_pe_fails_before_xref_triage(self):
        binary, sha, idf, api, graph = fixture()
        modified = bytearray(binary)
        modified[0x220] = 0x90
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            analyze_verified(bytes(modified), sha, idf, api, graph)

    def test_mismatched_xref_identity_rejected(self):
        binary, sha, idf, api, graph = fixture()
        api['source_md5'] = '0' * 32
        with self.assertRaisesRegex(ValueError, 'source MD5'):
            analyze_verified(binary, sha, idf, api, graph)

    def test_cli_writes_only_aggregate_json(self):
        binary, sha, idf, api, graph = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name for name in ('original.exe', 'idf.json', 'api.json', 'graph.json')]
            paths[0].write_bytes(binary)
            for path, report in zip(paths[1:], (idf, api, graph)):
                path.write_text(json.dumps(report), encoding='utf-8')
            output = root / 'public.json'
            argv = ['--pe', str(paths[0]), '--expected-sha256', sha,
                    '--idf-private-report', str(paths[1]),
                    '--api-private-report', str(paths[2]),
                    '--callgraph-private-report', str(paths[3]),
                    '--public-output', str(output)]
            main(argv)
            data = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(data['schema'], 'atelierdata-ghidra-idf-verified-triage-v1')
            self.assertNotIn('004010', output.read_text(encoding='utf-8'))
            with self.assertRaises(SystemExit):
                main(argv[:-1] + [str(paths[0])])

    def test_partial_graph_remains_explicitly_partial(self):
        binary, sha, idf, api, graph = fixture()
        graph['coverage_truncated'] = True
        report = analyze_verified(binary, sha, idf, api, graph)
        self.assertTrue(report['callgraph_coverage_truncated'])
        self.assertFalse(report['runtime_reachability_proven'])


if __name__ == '__main__':
    unittest.main()
