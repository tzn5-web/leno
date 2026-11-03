"""Synthetic regression: failed atomic publication must preserve existing output."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ghidra_idf_api_correlation as module


class AtomicPublishTests(unittest.TestCase):
    def test_failed_replace_preserves_existing_summary_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            idf = folder / "idf-private.json"
            api = folder / "api-private.json"
            output = folder / "public.json"
            idf.write_text("{}", encoding="utf-8")
            api.write_text("{}", encoding="utf-8")
            output.write_text("previous verified summary", encoding="utf-8")
            args = ["correlate", "--idf-private-report", str(idf),
                    "--api-private-report", str(api),
                    "--expected-sha256", "a" * 64,
                    "--public-output", str(output)]
            with mock.patch.object(sys, "argv", args), \
                 mock.patch.object(module, "load_private", return_value={}), \
                 mock.patch.object(module, "correlate", return_value={"safe": True}), \
                 mock.patch.object(module.os, "replace", side_effect=OSError("disk error")):
                with self.assertRaisesRegex(OSError, "disk error"):
                    module.main()
            self.assertEqual(output.read_text(encoding="utf-8"), "previous verified summary")
            self.assertEqual(list(folder.glob(".atelierdata-summary-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
