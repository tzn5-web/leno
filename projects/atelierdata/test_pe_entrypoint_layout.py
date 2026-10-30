"""Deterministic synthetic tests. Original executable never enters CI."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from pe_entrypoint_layout import analyze_layout, run, entropy, windows
from test_pe_file_io_xrefs import sample_pe


class PEEntrypointLayoutTests(unittest.TestCase):
    def test_entropy_known_values(self):
        self.assertEqual(entropy(b'\0' * 100), 0.0)
        self.assertEqual(entropy(b'\0\1' * 100), 1.0)
        self.assertEqual(windows(b''), [])

    def test_synthetic_entrypoint_and_iat(self):
        blob = bytearray(sample_pe())
        struct.pack_into('<I', blob, 0x98 + 16, 0x1000)
        data = bytes(blob)
        report = analyze_layout(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(report['entrypoint_section_index'], 0)
        self.assertEqual(report['iat_candidate_total'], 1)
        self.assertEqual(report['iat_candidates_in_entrypoint_section'], 1)
        self.assertFalse(report['loader_wrapper_hypothesis'])
        self.assertFalse(report['decoder_proven'])
        self.assertNotIn('instruction_va', json.dumps(report))

    def test_sha_and_entrypoint_rejection(self):
        data = bytearray(sample_pe())
        struct.pack_into('<I', data, 0x98 + 16, 0x1000)
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            analyze_layout(bytes(data), '0' * 64)
        struct.pack_into('<I', data, 0x98 + 16, 0x90000000)
        with self.assertRaisesRegex(ValueError, 'Entrypoint not mapped'):
            analyze_layout(bytes(data), hashlib.sha256(data).hexdigest())

    def test_file_report_and_overlay(self):
        data = bytearray(sample_pe())
        struct.pack_into('<I', data, 0x98 + 16, 0x1000)
        data += b'private synthetic overlay'
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp) / 'fixture.exe', Path(tmp) / 'public.json'
            src.write_bytes(data)
            report = run(src, hashlib.sha256(data).hexdigest(), dest)
            self.assertEqual(report['overlay_bytes'], len(data) - 0x600)
            self.assertEqual(json.loads(dest.read_text())['sha256'], report['sha256'])


if __name__ == '__main__':
    unittest.main()
