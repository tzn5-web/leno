"""Synthetic-only tests; no private Autodata content in repository or CI."""
import copy
import hashlib
import json
import struct
import unittest

from ghidra_iat_instruction_evidence import verify


def fixture():
    b = bytearray(1024)
    b[:2] = b'MZ'
    struct.pack_into('<I', b, 0x3c, 0x80)
    b[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', b, 0x84, 0x14c, 1, 0, 0, 0, 224, 0x0102)
    opt = 0x98
    struct.pack_into('<H', b, opt, 0x10b)
    struct.pack_into('<I', b, opt+28, 0x400000)
    section = opt+224
    b[section:section+8] = b'.text\0\0\0'
    struct.pack_into('<IIII', b, section+8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into('<I', b, section+36, 0x60000020)
    b[0x220:0x226] = b'\xff\x15' + struct.pack('<I', 0x4020c0)
    return bytes(b)


def evidence():
    data = fixture()
    sha = hashlib.sha256(data).hexdigest()
    iat = {'schema': 'atelierdata-pe-iat-private-v1', 'sha256': sha,
           'candidates': [{'instruction_va': 0x401020, 'file_offset': 0x220,
                           'iat_va': 0x4020c0, 'kind': 'call', 'symbol': 'LoadLibraryA'}]}
    ghidra = {'schema': 'atelierdata-ghidra-iat-instruction-check-v1', 'source_sha256': sha,
              'program_name': 'synthetic.exe', 'candidate_count': 1,
              'recognized_instruction_count': 1, 'instructions_with_references': 1,
              'candidates': [{'address': '00401020', 'symbol': 'LoadLibraryA',
                              'in_memory': True, 'recognized_instruction': True,
                              'mnemonic': 'CALL', 'references_from_instruction': 1}]}
    return data, sha, iat, ghidra


class IATEvidenceTests(unittest.TestCase):
    def test_verified_recognized_call(self):
        data, sha, iat, ghidra = evidence()
        result = verify(data, sha, iat, ghidra)
        self.assertEqual(result['recognized_calls'], 1)
        self.assertEqual(result['raw_iat_candidate_bytes_verified'], 1)
        self.assertFalse(result['idf_decoder_proven'])
        self.assertFalse(result['ghidra_imported_program_identity_independently_verified'])
        self.assertNotIn('LoadLibraryA', json.dumps(result))
        self.assertNotIn('00401020', json.dumps(result))

    def test_unrecognized_candidate_remains_valid_evidence(self):
        data, sha, iat, ghidra = evidence()
        ghidra['candidates'][0].update(recognized_instruction=False, mnemonic=None,
                                       references_from_instruction=0)
        ghidra['recognized_instruction_count'] = 0
        ghidra['instructions_with_references'] = 0
        result = verify(data, sha, iat, ghidra)
        self.assertEqual(result['ghidra_unrecognized_candidates'], 1)

    def test_reject_modified_executable(self):
        data, sha, iat, ghidra = evidence()
        with self.assertRaises(ValueError):
            verify(data[:-1]+b'X', sha, iat, ghidra)

    def test_reject_wrong_report_sha(self):
        data, sha, iat, ghidra = evidence()
        ghidra['source_sha256'] = '0'*64
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_wrong_file_offset(self):
        data, sha, iat, ghidra = evidence()
        iat['candidates'][0]['file_offset'] = 0x221
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_wrong_target_operand(self):
        data, sha, iat, ghidra = evidence()
        iat['candidates'][0]['iat_va'] += 4
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_forged_ghidra_address(self):
        data, sha, iat, ghidra = evidence()
        ghidra['candidates'][0]['address'] = '00401021'
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_forged_recognition_count(self):
        data, sha, iat, ghidra = evidence()
        ghidra['recognized_instruction_count'] = 0
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_false_boolean_as_integer(self):
        data, sha, iat, ghidra = evidence()
        ghidra['candidate_count'] = True
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_duplicate_candidate(self):
        data, sha, iat, ghidra = evidence()
        iat['candidates'].append(copy.deepcopy(iat['candidates'][0]))
        ghidra['candidates'].append(copy.deepcopy(ghidra['candidates'][0]))
        ghidra['candidate_count'] = 2
        ghidra['recognized_instruction_count'] = 2
        ghidra['instructions_with_references'] = 2
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_unmapped_candidate(self):
        data, sha, iat, ghidra = evidence()
        iat['candidates'][0]['instruction_va'] = 0x500000
        ghidra['candidates'][0]['address'] = '00500000'
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_contradictory_mnemonic(self):
        data, sha, iat, ghidra = evidence()
        ghidra['candidates'][0]['mnemonic'] = 'JMP'
        with self.assertRaises(ValueError):
            verify(data, sha, iat, ghidra)

    def test_reject_invalid_pe(self):
        data, sha, iat, ghidra = evidence()
        bad = bytearray(data)
        bad[0x80] = 0
        bad = bytes(bad)
        iat['sha256'] = hashlib.sha256(bad).hexdigest()
        ghidra['source_sha256'] = iat['sha256']
        with self.assertRaises(ValueError):
            verify(bad, iat['sha256'], iat, ghidra)

    def test_zero_candidates(self):
        data, sha, iat, ghidra = evidence()
        iat['candidates'] = []
        ghidra['candidates'] = []
        ghidra['candidate_count'] = 0
        ghidra['recognized_instruction_count'] = 0
        ghidra['instructions_with_references'] = 0
        self.assertEqual(verify(data, sha, iat, ghidra)['raw_iat_candidate_bytes_verified'], 0)


if __name__ == '__main__':
    unittest.main()
