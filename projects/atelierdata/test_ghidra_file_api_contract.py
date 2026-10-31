"""Synthetic-only checks of the Ghidra API xref script contract.

No Ghidra installation, private executable or .IDF data is used here.
The tests exercise the actual canonical_api function extracted from the script,
not a reimplementation. They do NOT constitute Ghidra runtime validation.
"""
import ast
import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_File_API_Xrefs.py"


def load_normalizer():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    chosen = [node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "canonical_api"]
    constants = [node for node in tree.body
                 if isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "API_NAMES"
                     for target in node.targets)]
    if len(chosen) != 1 or len(constants) != 1:
        raise AssertionError("API normalizer or allowlist missing")
    module = ast.Module(body=constants + chosen, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"re": re}
    exec(compile(module, str(SCRIPT), "exec"), namespace)
    return namespace["canonical_api"]


class GhidraApiSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")
        cls.normalize = staticmethod(load_normalizer())

    def test_decorated_import_names(self):
        for spelling in ("ReadFile", "_ReadFile@20", "__imp_ReadFile",
                         "__imp__ReadFile@20"):
            self.assertEqual(self.normalize(spelling), "ReadFile")
        for spelling in ("__imp_CreateFileW@28", "_LoadLibraryA@4",
                         "SetFilePointerEx"):
            self.assertIsNotNone(self.normalize(spelling))

    def test_reject_unrelated_names(self):
        for spelling in ("ReadFileEvil", "MyReadFile", "ReadFile@oops",
                         "__imp_ReadFile@20extra", "CryptDecryptMessage"):
            self.assertIsNone(self.normalize(spelling))

    def test_original_and_imported_hashes_are_checked(self):
        for required in ("hashlib.sha256()", "hashlib.md5()",
                         "sha.hexdigest() != expected",
                         "currentProgram.getExecutableSHA256()",
                         "currentProgram.getExecutableMD5()",
                         "imported_md5.lower() != md5.hexdigest()"):
            self.assertIn(required, self.text)

    def test_private_output_and_bounded_scan(self):
        for required in ("os.path.islink(source)", "os.path.islink(output)",
                         "MAX_PE_BYTES", "MAX_SYMBOLS", "MAX_REFS",
                         "MAX_REFS_PER_SYMBOL", '"private_only": True',
                         '"idf_decoder_proven": False',
                         '"target_executed": False'):
            self.assertIn(required, self.text)

    def test_existing_ghidra_api_methods(self):
        for required in ("getAllSymbols(False)", "getReferencesTo(addr)",
                         "getFunctionContaining(src)",
                         "getInstructionContaining(src)"):
            self.assertIn(required, self.text)


if __name__ == "__main__":
    unittest.main()
