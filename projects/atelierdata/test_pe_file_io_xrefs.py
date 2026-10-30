"""Synthetic PE32 fixture; no original binaries required for CI."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from pe_file_io_xrefs import analyze, parse_pe32, run


def sample_pe():
    b = bytearray(1536)
    b[:2] = b'MZ'
    struct.pack_into('<I', b, 0x3c, 0x80)
    b[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', b, 0x84, 0x14c, 2, 0, 0, 0, 224, 0x0102)
    opt = 0x98
    struct.pack_into('<H', b, opt, 0x10b)
    struct.pack_into('<I', b, opt + 28, 0x400000)
    struct.pack_into('<I', b, opt + 60, 0x200)
    struct.pack_into('<I', b, opt + 92, 16)
    struct.pack_into('<II', b, opt + 104, 0x2020, 40)
    sec = opt + 224
    b[sec:sec + 8] = b'.text\0\0\0'
    struct.pack_into('<IIII', b, sec + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into('<I', b, sec + 36, 0x60000020)
    sec += 40
    b[sec:sec + 8] = b'.idata\0\0'
    struct.pack_into('<IIII', b, sec + 8, 0x200, 0x2000, 0x200, 0x400)
    struct.pack_into('<I', b, sec + 36, 0x40000040)
    struct.pack_into('<IIIII', b, 0x420, 0x20a0, 0, 0, 0x2080, 0x20c0)
    b[0x480:0x48d] = b'KERNEL32.dll\0'
    struct.pack_into('<II', b, 0x4a0, 0x20e0, 0)
    struct.pack_into('<II', b, 0x4c0, 0x20e0, 0)
    b[0x4e2:0x4ee] = b'LoadLibraryA\0'
    b[0x220:0x226] = b'\xff\x15' + struct.pack('<I', 0x4020c0)
    b[0x240:0x24d] = b'CreateFileA\0\0'
    return bytes(b)


class IATStaticTriageTests(unittest.TestCase):
    def test_pe32_import_and_callsite(self):
        data = sample_pe()
        digest = hashlib.sha256(data).hexdigest()
        public, private = analyze(data, digest)
        self.assertEqual(public['imported_symbol_count'], 1)
        self.assertEqual(public['candidate_count'], 1)
        self.assertEqual(public['focus_candidates']['kernel32.dll!LoadLibraryA:call'], 1)
        self.assertEqual(public['literal_probes']['CreateFileA']['ascii']['literal_count_at_most_1024'], 1)
        self.assertEqual(private['candidates'][0]['file_offset'], 0x220)
        self.assertEqual(private['candidates'][0]['iat_va'], 0x4020c0)
        self.assertNotIn('iat_va', json.dumps(public))
        self.assertFalse(public['idf_decoder_proven'])
        self.assertNotIn('file_offset', json.dumps(public))

    def test_wrong_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            analyze(sample_pe(), '0' * 64)

    def test_malformed_pe_rejected(self):
        data = bytearray(sample_pe())
        data[0x80] = 0
        with self.assertRaises(ValueError):
            parse_pe32(data)
        data = bytearray(sample_pe())
        struct.pack_into('<I', data, 0x420, 0xffffffff)
        with self.assertRaises(ValueError):
            parse_pe32(data)

    def test_private_public_separation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'sample.exe'
            source.write_bytes(sample_pe())
            pub, private = root / 'public.json', root / 'private.json'
            result = run(source, hashlib.sha256(source.read_bytes()).hexdigest(), pub, private)
            self.assertEqual(result['candidate_count'], 1)
            self.assertNotIn('file_offset', pub.read_text())
            self.assertIn('file_offset', private.read_text())
            with self.assertRaisesRegex(ValueError, 'must differ'):
                run(source, hashlib.sha256(source.read_bytes()).hexdigest(), pub, pub)
            with self.assertRaisesRegex(ValueError, 'must differ'):
                run(source, hashlib.sha256(source.read_bytes()).hexdigest(), source, private)
            with self.assertRaisesRegex(ValueError, 'must differ'):
                run(source, hashlib.sha256(source.read_bytes()).hexdigest(), pub, source)
            self.assertEqual(source.read_bytes(), sample_pe())


if __name__ == '__main__':
    unittest.main()
