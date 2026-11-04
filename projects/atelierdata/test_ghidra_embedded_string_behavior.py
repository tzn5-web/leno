"""Behavioral synthetic tests of the real Ghidra scanner, without Ghidra or target execution."""
import ast
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_IDF_Xrefs.py"

class Address:
    def __init__(self, value): self.value = value
    def add(self, offset): return Address(self.value + offset)
    def __str__(self): return "RAM:%08x" % self.value

class Block:
    def __init__(self, content): self.content = content
    def getSize(self): return len(self.content)
    def isInitialized(self): return True
    def getStart(self): return Address(0x1000)

class Memory:
    def __init__(self, content): self.content = content
    def getBytes(self, address, buffer):
        start = address.value - 0x1000
        chunk = self.content[start:start + len(buffer)]
        for i, b in enumerate(chunk):
            buffer[i] = b if b < 128 else b - 256
        return len(chunk)

class RefType:
    def __str__(self): return "DATA"
    def isData(self): return True

class Reference:
    def getFromAddress(self): return Address(0x4000)
    def getReferenceType(self): return RefType()

class ReferenceManager:
    def __init__(self, target): self.target = target
    def getReferencesTo(self, address):
        return [Reference()] if address.value == self.target else []

class Data:
    def getMinAddress(self): return Address(0x1000)

class Monitor:
    def checkCanceled(self): pass

class Program:
    def __init__(self, content): self.memory = Memory(content)
    def getMemory(self): return self.memory

def scan(content, target, containing=True):
    source = SCRIPT.read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(source).body
              if isinstance(n, ast.FunctionDef) and n.name == "scan_block")
    module = ast.Module(body=[fn], type_ignores=[])
    env = {
        "TERMS": ("MODELS.IDF",), "MAX_SCAN_BYTES": 128 * 1024 * 1024,
        "MAX_MATCHES_PER_TERM": 32, "MAX_XREFS_PER_MATCH": 16,
        "zeros": lambda n, kind: [0] * n,
        "monitor": Monitor(), "currentProgram": Program(content),
        "getDataContaining": lambda addr: Data() if containing else None,
        "getFunctionContaining": lambda addr: None,
        "getInstructionAt": lambda addr: None,
    }
    exec(compile(module, str(SCRIPT), "exec"), env)
    return env["scan_block"](Block(content), ReferenceManager(target))

class EmbeddedStringBehavior(unittest.TestCase):
    def test_containing_string_start(self):
        content = b"prefix-MODELS.IDF-suffix\\x00"
        hits, scanned = scan(content, 0x1000)
        self.assertEqual(scanned, len(content))
        refs = hits["MODELS.IDF:ascii"][0]["references_from"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["reference_target_provenance"], "containing_data_start")

    def test_exact_reference(self):
        hits, _ = scan(b"prefix-MODELS.IDF", 0x1007)
        refs = hits["MODELS.IDF:ascii"][0]["references_from"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["reference_target_provenance"], "exact_match")

    def test_no_containing_data_no_fabricated_reference(self):
        hits, _ = scan(b"prefix-MODELS.IDF", 0x1000, containing=False)
        self.assertEqual(hits["MODELS.IDF:ascii"][0]["references_from"], [])

if __name__ == "__main__":
    unittest.main()
