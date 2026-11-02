"""Synthetic-only regression for byte-corroborated IDF source hop tiers.

A Ghidra-claimed path must not become a verified-literal path unless the
original PE bytes actually contain the claimed .IDF string at its VA.
API endpoints remain Ghidra-reported and are not independently replayed.
"""
import hashlib
import json
import struct
import unittest

from ghidra_verified_idf_triage import analyze_verified
from test_ghidra_verified_idf_triage import fixture


def with_literal(pointer=False, boundary=False):
    binary, _, idf, api, graph = fixture()
    data = bytearray(binary)
    data[0x280:0x28a] = b'MODELS.IDF'
    if pointer:
        data[0x290:0x295] = bytes((0x68,)) + struct.pack('<I', 0x401080)
    binary = bytes(data)
    sha = hashlib.sha256(binary).hexdigest()
    md5 = hashlib.md5(binary).hexdigest()
    for report in (idf, api, graph):
        report['source_sha256'] = sha
        report['source_md5'] = md5
    hit = idf['keyword_hits']['.rdata']['MODELS.IDF:ascii'][0]
    hit['address'] = '00401080'
    ref = hit['references_from'][0]
    if pointer:
        ref['source_address'] = '00401090'
    if boundary:
        ref.update({
            'reference_type': 'DATA',
            'reference_is_data': True,
            'instruction_start_address': '00401090',
            'instruction_length': 5,
            'instruction_mnemonic': 'PUSH',
        })
    return binary, sha, idf, api, graph


class VerifiedSourceDistanceTiersTests(unittest.TestCase):
    def test_mismatched_literal_never_upgrades_legacy_ghidra_hops(self):
        binary, sha, idf, api, graph = fixture()
        result = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(result['idf_sources_by_shortest_direct_file_io_hops']['1'], 1)
        self.assertEqual(
            result['verified_literal_sources_by_shortest_ghidra_file_io_hops']['1'], 0)
        self.assertEqual(result['verified_literal_source_function_count'], 0)
        self.assertTrue(result['idf_report_derived_hops_include_unverified_literal_xrefs'])
        self.assertFalse(result['api_endpoint_calls_independently_replayed'])

    def test_valid_literal_corroborates_source_but_not_pointer(self):
        binary, sha, idf, api, graph = with_literal()
        result = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(result['verified_literal_source_function_count'], 1)
        self.assertEqual(
            result['verified_literal_sources_by_shortest_ghidra_file_io_hops']['1'], 1)
        self.assertEqual(
            result['verified_raw_pointer_sources_by_shortest_ghidra_file_io_hops']['1'], 0)
        self.assertFalse(result['idf_decoder_proven'])

    def test_pointer_and_ghidra_instruction_boundary_have_separate_tiers(self):
        binary, sha, idf, api, graph = with_literal(pointer=True)
        raw = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(
            raw['verified_raw_pointer_sources_by_shortest_ghidra_file_io_hops']['1'], 1)
        self.assertEqual(
            raw['verified_boundary_pointer_sources_by_shortest_ghidra_file_io_hops']['1'], 0)
        binary, sha, idf, api, graph = with_literal(pointer=True, boundary=True)
        boundary = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(
            boundary['verified_boundary_pointer_sources_by_shortest_ghidra_file_io_hops']['1'], 1)
        self.assertNotIn('00401080', json.dumps(boundary))

    def test_dynamic_lookup_is_not_direct_file_io(self):
        binary, sha, idf, api, graph = with_literal()
        api['api_symbols']['GetProcAddress'] = api['api_symbols'].pop('ReadFile')
        result = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(
            result['verified_literal_sources_by_shortest_ghidra_file_io_hops']['1'], 0)
        self.assertEqual(
            result['verified_literal_sources_by_shortest_ghidra_dynamic_lookup_hops']['1'], 1)


if __name__ == '__main__':
    unittest.main()
