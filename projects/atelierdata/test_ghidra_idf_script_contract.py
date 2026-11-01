"""Static source contract for private Ghidra IDF xref exporter.

This does NOT execute Ghidra or the original program. It prevents accidental
removal of identity checks and xref instruction metadata during refactors.
"""
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_IDF_Xrefs.py"


class GhidraIDFScriptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_original_identity_is_required(self):
        self.assertIn("currentProgram.getExecutableSHA256()", self.source)
        self.assertIn("currentProgram.getExecutableMD5()", self.source)
        self.assertIn("ghidra_import_sha256_verified", self.source)
        self.assertIn("executed_target_binary", self.source)

    def test_xref_instruction_and_reference_metadata_is_exported(self):
        self.assertIn("ref.getReferenceType()", self.source)
        self.assertIn("getInstructionAt(source)", self.source)
        for field in ("reference_type", "reference_is_data",
                      "instruction_start_address", "instruction_length",
                      "instruction_mnemonic"):
            with self.subTest(field=field):
                self.assertIn("'" + field + "'", self.source)

    def test_bounded_scan_and_private_report(self):
        self.assertIn("MAX_SCAN_BYTES", self.source)
        self.assertIn("MAX_MATCHES_PER_TERM", self.source)
        self.assertIn("MAX_XREFS_PER_MATCH", self.source)
        self.assertIn("destination = args[0]", self.source)
        self.assertIn("'idf_decoder_proven': False", self.source)


if __name__ == "__main__":
    unittest.main()
