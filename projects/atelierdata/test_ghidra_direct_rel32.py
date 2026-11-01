"""Test the actual Ghidra exporter's pure E8 rel32 decoder with synthetic bytes.

The Ghidra script is never executed or imported; only the isolated arithmetic
function is compiled from its AST. No proprietary binary or .IDF is accessed.
"""
import ast
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_Direct_Callgraph.py"


def load_decoder():
    module = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    functions = [node for node in module.body
                 if isinstance(node, ast.FunctionDef) and node.name == "verified_rel32"]
    if len(functions) != 1:
        raise AssertionError("Exactly one pure verified_rel32 function is required")
    isolated = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    namespace = {}
    exec(compile(isolated, str(SCRIPT), "exec"), namespace)
    return namespace["verified_rel32"]


class DirectRel32Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verify = staticmethod(load_decoder())

    @staticmethod
    def call_bytes(site, target):
        displacement = target - (site + 5)
        return [0xe8] + list(displacement.to_bytes(4, "little", signed=True))

    def test_forward_call_matches(self):
        site, target = 0x401000, 0x402000
        self.assertTrue(self.verify(self.call_bytes(site, target), site, target))

    def test_backward_call_matches(self):
        site, target = 0x402000, 0x401000
        self.assertTrue(self.verify(self.call_bytes(site, target), site, target))

    def test_target_mismatch_rejected(self):
        site, target = 0x401000, 0x402000
        self.assertFalse(self.verify(self.call_bytes(site, target), site, target + 1))

    def test_non_call_opcode_rejected(self):
        site, target = 0x401000, 0x402000
        raw = self.call_bytes(site, target)
        raw[0] = 0xe9  # JMP rel32 is not a CALL
        self.assertFalse(self.verify(raw, site, target))

    def test_short_and_long_instructions_rejected(self):
        site, target = 0x401000, 0x402000
        raw = self.call_bytes(site, target)
        self.assertFalse(self.verify(raw[:4], site, target))
        self.assertFalse(self.verify(raw + [0], site, target))

    def test_signed_negative_displacement(self):
        site = 0x401000
        target = site + 5 - 1
        self.assertTrue(self.verify([0xe8, 0xff, 0xff, 0xff, 0xff], site, target))


if __name__ == "__main__":
    unittest.main()
