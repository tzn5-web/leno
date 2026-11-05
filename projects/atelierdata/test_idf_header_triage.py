"""Synthetic-only tests for IDF metadata triage; no proprietary fixtures."""
import hashlib
import json
import os
import sys
from unittest.mock import patch
import tempfile
import unittest
from pathlib import Path
from idf_header_triage import inspect, main


class TestIdfHeaderTriage(unittest.TestCase):
    def test_verified_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            data = bytes(range(256)) * 4
            path.write_bytes(data)
            result = inspect(path, hashlib.sha256(data).hexdigest())
            self.assertTrue(result["sha256_verified"])
            self.assertEqual(result["size_bytes"], len(data))
            self.assertEqual(result["sample_entropy_bits_per_byte"], 8.0)
            self.assertFalse(result["format_identified"])
            self.assertFalse(result["decoder_verified"])

    def test_empty_file_has_finite_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.idf"
            path.write_bytes(b"")
            result = inspect(path, hashlib.sha256(b"").hexdigest())
            self.assertEqual(result["size_bytes"], 0)
            self.assertEqual(result["sample_bytes"], 0)
            self.assertEqual(result["sample_entropy_bits_per_byte"], 0.0)

    def test_sample_is_bounded_independently_of_file_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.idf"
            data = b"ABCD" * 20000
            path.write_bytes(data)
            result = inspect(path, hashlib.sha256(data).hexdigest(), sample_size=64)
            self.assertEqual(result["size_bytes"], len(data))
            self.assertEqual(result["sample_bytes"], 64)

    def test_same_size_in_place_change_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            data = b"synthetic-static-sample"
            path.write_bytes(data)
            real_fstat = os.fstat
            calls = 0

            def changed_fstat(fd):
                nonlocal calls
                calls += 1
                result = real_fstat(fd)
                if calls == 2:
                    os.utime(path, ns=(result.st_atime_ns, result.st_mtime_ns + 2_000_000_000))
                    return real_fstat(fd)
                return result

            with patch("idf_header_triage.os.fstat", side_effect=changed_fstat):
                with self.assertRaisesRegex(ValueError, "source changed during triage"):
                    inspect(path, hashlib.sha256(data).hexdigest())

    def test_wrong_digest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            path.write_bytes(b"sample")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                inspect(path, "0" * 64)

    def test_invalid_sample_size_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            path.write_bytes(b"")
            with self.assertRaises(ValueError):
                inspect(path, hashlib.sha256(b"").hexdigest(), 65537)

    def test_existing_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.idf"
            source.write_bytes(b"synthetic")
            report = root / "report.json"
            report.write_text("sentinel", encoding="utf-8")
            argv = ["idf_header_triage.py", "--file", str(source),
                    "--expected-sha256", hashlib.sha256(b"synthetic").hexdigest(),
                    "--output", str(report)]
            with patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
                main()
            self.assertEqual(report.read_text(encoding="utf-8"), "sentinel")

    def test_new_report_created_exclusively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.idf"
            source.write_bytes(b"synthetic")
            report = root / "report.json"
            argv = ["idf_header_triage.py", "--file", str(source),
                    "--expected-sha256", hashlib.sha256(b"synthetic").hexdigest(),
                    "--output", str(report)]
            with patch.object(sys, "argv", argv):
                main()
            self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["sha256_verified"])

    def test_output_symlink_does_not_overwrite_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.idf"
            source.write_bytes(b"synthetic")
            target = root / "target.json"
            target.write_text("sentinel", encoding="utf-8")
            report = root / "report.json"
            try:
                report.symlink_to(target)
            except OSError:
                self.skipTest("symlink unavailable")
            argv = ["idf_header_triage.py", "--file", str(source),
                    "--expected-sha256", hashlib.sha256(b"synthetic").hexdigest(),
                    "--output", str(report)]
            with patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
                main()
            self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            path.write_bytes(b"sample")
            link = Path(directory) / "alias.idf"
            try:
                link.symlink_to(path)
            except OSError:
                self.skipTest("symlink unavailable")
            with self.assertRaises(ValueError):
                inspect(link, hashlib.sha256(b"sample").hexdigest())


if __name__ == "__main__":
    unittest.main()
