"""Synthetic-only tests; no proprietary files or original executable required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from original_windows_path_gate import ROOT, audit_paths, load_paths, main

class WindowsPathGateTests(unittest.TestCase):
    def test_valid_inventory(self):
        r = audit_paths([(ROOT + "/ADCDA2/COMMON/A.IDF", 100), (ROOT + "/ADCDA2/app.exe", 7)])
        self.assertEqual(r["state"], "WINDOWS_PATH_NAMES_COMPATIBLE")
        self.assertEqual((r["file_count"], r["total_declared_bytes"], r["idf_file_count"]), (2, 107, 1))
        self.assertFalse(r["original_installation_ready"])

    def test_case_insensitive_collision(self):
        r = audit_paths([(ROOT + "/ABC.idf", 1), (ROOT + "/abc.IDF", 2)])
        self.assertEqual(r["issues"]["windows_casefold_collision"], 1)

    def test_path_traversal(self):
        r = audit_paths([(ROOT + "/../bad", 1), ("/absolute", 1)])
        self.assertEqual(r["issues"]["unsafe_relative_path"], 2)

    def test_windows_device_names(self):
        r = audit_paths([(ROOT + "/CON.txt", 1), (ROOT + "/COM1", 1), (ROOT + "/LPT².bin", 1)])
        self.assertEqual(r["issues"]["reserved_windows_device_name"], 3)

    def test_trailing_dots_and_invalid_characters(self):
        r = audit_paths([(ROOT + "/a. ", 1), (ROOT + "/bad:name", 1)])
        self.assertEqual(r["issues"]["trailing_dot_or_space"], 1)
        self.assertEqual(r["issues"]["invalid_windows_character"], 1)

    def test_long_path_utf16(self):
        r = audit_paths([(ROOT + "/" + "a" * 250, 1)])
        self.assertEqual(r["issues"]["long_relative_path"], 1)

    def test_txt_json_equivalent(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            p = ROOT + "/ADCDA2/COMMON/A.IDF"
            (d / "INVENTAR.txt").write_text(f"    4 {p}\n", encoding="utf8")
            (d / "INVENTAR.json").write_text(json.dumps({"files": [{"path": p, "size_bytes": 4}]}), encoding="utf8")
            self.assertEqual(load_paths(d / "INVENTAR.txt"), load_paths(d / "INVENTAR.json"))

    def test_invalid_inventory_line_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "INVENTAR.txt"
            p.write_text("INVALID", encoding="utf8")
            with self.assertRaises(ValueError):
                load_paths(p)

    def test_empty_inventory_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            audit_paths([])

    def test_negative_size_rejected(self):
        with self.assertRaises(ValueError):
            audit_paths([(ROOT + "/a", -1)])

    def test_output_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "INVENTAR.txt"
            p.write_text(" 4 " + ROOT + "/a\n", encoding="utf8")
            before = p.read_bytes()
            with patch("sys.argv", ["tool", "--inventory", str(p), "--output", str(p)]):
                self.assertEqual(main(), 2)
            self.assertEqual(p.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
