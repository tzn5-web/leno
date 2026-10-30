"""Static source contract for Ghidra helper; NOT a Ghidra execution test."""
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_IAT_Verified.java"


class GhidraScriptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_original_identity_is_checked(self):
        self.assertIn("MessageDigest.getInstance(\"SHA-256\")", self.source)
        self.assertIn("currentProgram.getExecutableMD5()", self.source)
        self.assertIn("Original PE SHA256 mismatch", self.source)

    def test_report_output_paths_are_canonical_and_distinct(self):
        self.assertIn("getCanonicalFile()", self.source)
        self.assertIn("privateOutput.equals(originalInput)", self.source)
        self.assertIn("publicOutput.equals(originalInput)", self.source)
        self.assertIn("publicOutput.equals(privateInput)", self.source)
        self.assertIn("publicOutput.equals(privateOutput)", self.source)
        self.assertNotIn("new FileWriter(args[", self.source)

    def test_static_instruction_verification_not_decoder(self):
        self.assertIn("instruction.getLength() == 6", self.source)
        self.assertIn("operand == iatVa", self.source)
        self.assertIn("idf_decoder_proven", self.source)
        self.assertIn("target_executed", self.source)


if __name__ == "__main__":
    unittest.main()
