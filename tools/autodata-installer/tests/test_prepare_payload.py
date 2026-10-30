import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_payload import load_allowlist, stage


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.src = self.base / "licensed"
        (self.src / "ADCDA2" / "COMMON").mkdir(parents=True)
        (self.src / "ADCDA2" / "ADBCD.exe").write_bytes(b"synthetic executable placeholder")
        (self.src / "ADCDA2" / "COMMON" / "TEST.IDF").write_bytes(b"synthetic data")
        (self.src / "Keygen").mkdir()
        (self.src / "Keygen" / "license.exe").write_bytes(b"do not copy")
        self.allow = [
            {"path": "ADCDA2/ADBCD.exe", "size_bytes": 32},
            {"path": "ADCDA2/COMMON/TEST.IDF", "size_bytes": 14},
        ]
        # Use actual fixture sizes; don't rely on hardcoded text lengths.
        for row in self.allow:
            row["size_bytes"] = (self.src / row["path"]).stat().st_size

    def test_only_allowlisted_files_staged(self):
        output = self.base / "output"
        result = stage(self.src, output, self.allow, dry_run=False)
        self.assertEqual(result["status"], "STAGED_PASS")
        self.assertEqual(result["source_file_count"], 2)
        self.assertTrue((output / "ADCDA2" / "ADBCD.exe").is_file())
        self.assertFalse((output / "Keygen").exists())
        self.assertTrue((output / "staged_sha256.json").is_file())

    def test_wrong_size_refused(self):
        self.allow[0]["size_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "Size mismatch"):
            stage(self.src, self.base / "output", self.allow, dry_run=False)
        self.assertFalse((self.base / "output").exists())

    def test_dry_run_no_output(self):
        output = self.base / "output"
        result = stage(self.src, output, self.allow, dry_run=True)
        self.assertEqual(result["status"], "DRY_RUN_PASS")
        self.assertFalse(output.exists())

    def test_traversal_and_duplicates_refused(self):
        manifest = self.base / "allow.json"
        for bad in [
            [{"path": "ADCDA2/../Keygen/license.exe", "size_bytes": 1}],
            [{"path": "Keygen/license.exe", "size_bytes": 1}],
            [{"path": "ADCDA2/ADBCD.exe", "size_bytes": 1},
             {"path": "adcda2/adbcd.EXE", "size_bytes": 1}],
        ]:
            manifest.write_text(json.dumps({"files": bad}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_allowlist(manifest)

    def test_missing_file_refused(self):
        (self.src / "ADCDA2" / "COMMON" / "TEST.IDF").unlink()
        with self.assertRaises(FileNotFoundError):
            stage(self.src, self.base / "output", self.allow, dry_run=False)


if __name__ == "__main__":
    unittest.main()
