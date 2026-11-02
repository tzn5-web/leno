"""Synthetic PE32 integration: complete API literals only, no original inputs."""
import hashlib
import unittest

from pe_file_io_xrefs import analyze
from test_pe_file_io_xrefs import sample_pe


def scan(data):
    return analyze(bytes(data), hashlib.sha256(bytes(data)).hexdigest())[0]


class PEFileIOLiteralIntegrationTests(unittest.TestCase):
    def test_existing_exact_ascii_import_and_literal(self):
        result = scan(sample_pe())
        self.assertEqual(result['literal_probes']['CreateFileA']['ascii']['literal_count_at_most_1024'], 1)
        self.assertIn('NUL-terminated', result['literal_matching_policy'])

    def test_suffix_must_not_be_counted_as_api_name(self):
        data = bytearray(sample_pe())
        data[0x240:0x24d] = b'CreateFileAX\0'
        result = scan(data)
        self.assertEqual(result['literal_probes']['CreateFileA']['ascii']['literal_count_at_most_1024'], 0)

    def test_prefix_must_not_be_counted_as_api_name(self):
        data = bytearray(sample_pe())
        data[0x240:0x24d] = b'\0' * 13
        data[0x260:0x260 + len(b'SomeReadFile\0')] = b'SomeReadFile\0'
        result = scan(data)
        self.assertEqual(result['literal_probes']['ReadFile']['ascii']['literal_count_at_most_1024'], 0)

    def test_utf16le_literal_is_counted_when_terminated(self):
        data = bytearray(sample_pe())
        encoded = 'ReadFile\0'.encode('utf-16le')
        data[0x260:0x260 + len(encoded)] = encoded
        result = scan(data)
        self.assertEqual(result['literal_probes']['ReadFile']['utf-16le']['literal_count_at_most_1024'], 1)
        self.assertFalse(result['literal_probes']['ReadFile']['utf-16le']['truncated'])


if __name__ == '__main__':
    unittest.main()
