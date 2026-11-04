"""Static contract tests for Ghidra embedded-string xref provenance.

These tests never import Ghidra or execute an analyzed binary.
"""
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_IDF_Xrefs.py"


class EmbeddedStringReferenceContract(unittest.TestCase):
    def test_containing_string_start_is_checked(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("getDataContaining(addr)", source)
        self.assertIn("getMinAddress()", source)
        self.assertIn("refs.getReferencesTo(site)", source)
        self.assertIn("sites = [(addr, 'exact_match')]", source)
        self.assertIn("(start, 'containing_data_start')", source)

    def test_provenance_and_reference_limit_are_preserved(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("'reference_target_provenance': provenance", source)
        self.assertIn("'reference_target_address': str(site)", source)
        self.assertIn("if len(xrefs) >= MAX_XREFS_PER_MATCH:", source)
        self.assertIn("keyword_xref_cap_reached", source)


if __name__ == "__main__":
    unittest.main()
