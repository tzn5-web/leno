"""Synthetic-only regression checks for cross-file stride evidence."""
import unittest
from unittest.mock import patch

from idf_stride_evidence import analyze


def sample(start, stride, count=12):
    data = bytearray(b"z" * (start + stride * count + 8))
    for i in range(count):
        at = start + i * stride
        data[at:at + 8] = b"ABCDEFGH"
    return bytes(data)


class CrossFileAlignmentTests(unittest.TestCase):
    def run_analysis(self, left, right):
        def get_chunk(manifest, directory, name):
            return (left if name == "SGOPS.IDF" else right), 1000
        with patch("idf_stride_evidence.first_verified_chunk", side_effect=get_chunk):
            return analyze({"files": []}, ".", ("SGOPS.IDF", "SGINT.IDF"))

    def test_same_token_different_offsets_not_aligned(self):
        report = self.run_analysis(sample(2, 21), sample(5, 21))
        self.assertTrue(report["sgops_sgint_same_dominant_token"])
        self.assertFalse(report["sgops_sgint_dominant_run_aligned"])
        self.assertFalse(report["idf_decoder_proven"])

    def test_same_token_different_stride_not_aligned(self):
        report = self.run_analysis(sample(2, 21), sample(2, 19))
        self.assertTrue(report["sgops_sgint_same_dominant_token"])
        self.assertFalse(report["sgops_sgint_dominant_run_aligned"])

    def test_identical_runs_aligned(self):
        report = self.run_analysis(sample(2, 21), sample(2, 21))
        self.assertTrue(report["sgops_sgint_dominant_run_aligned"])


if __name__ == "__main__":
    unittest.main()
