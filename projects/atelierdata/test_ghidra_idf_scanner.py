"""Synthetic-only tests of the real Ghidra scanner function, without Ghidra or private files."""
import ast
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_IDF_Xrefs.py"


class Address:
    def __init__(self, value):
        self.value = value

    def add(self, delta):
        return Address(self.value + delta)

    def __str__(self):
        return "%08x" % self.value


class Block:
    def __init__(self, data):
        self.data = data

    def getSize(self):
        return len(self.data)

    def getStart(self):
        return Address(0)

    def isInitialized(self):
        return True


class Memory:
    def __init__(self, data, stop_at=None):
        self.data = data
        self.stop_at = len(data) if stop_at is None else stop_at

    def getBytes(self, addr, buf):
        start = addr.value
        count = min(len(buf), max(0, self.stop_at - start))
        for index, value in enumerate(self.data[start:start + count]):
            buf[index] = value if value < 128 else value - 256
        return count


class Program:
    def __init__(self, data, stop_at=None):
        self.memory = Memory(data, stop_at)

    def getMemory(self):
        return self.memory


class Refs:
    def getReferencesTo(self, addr):
        return []


class Monitor:
    def checkCanceled(self):
        pass


def load_scanner(data, cap=None, stop_at=None):
    source = SCRIPT.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(SCRIPT))
    func = next(node for node in parsed.body
                if isinstance(node, ast.FunctionDef) and node.name == "scan_block")
    module = ast.Module(body=[func], type_ignores=[])
    namespace = {
        "MAX_SCAN_BYTES": len(data) if cap is None else cap,
        "MAX_MATCHES_PER_TERM": 32,
        "MAX_XREFS_PER_MATCH": 16,
        "TERMS": ("MODELS.IDF",),
        "zeros": lambda size, kind: [0] * size,
        "monitor": Monitor(),
        "currentProgram": Program(data, stop_at),
        # The Ghidra runtime supplies this helper; no defined data is present
        # in the synthetic byte-only scanner fixture.
        "getDataContaining": lambda addr: None,
    }
    exec(compile(module, str(SCRIPT), "exec"), namespace)
    return namespace["scan_block"]


class GhidraScannerSyntheticTests(unittest.TestCase):
    def test_boundary_spanning_match_is_not_duplicated(self):
        data = b"x" * (1024 * 1024 - 5) + b"MODELS.IDF" + b"tail"
        scanner = load_scanner(data)
        hits, scanned = scanner(Block(data), Refs())
        self.assertEqual(scanned, len(data))
        matches = hits["MODELS.IDF:ascii"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["address"], "%08x" % (1024 * 1024 - 5))

    def test_scan_byte_cap_is_reported_by_actual_offset(self):
        data = b"MODELS.IDF" + b"x" * 200
        scanner = load_scanner(data, cap=64)
        hits, scanned = scanner(Block(data), Refs())
        self.assertEqual(scanned, 64)
        self.assertEqual(len(hits["MODELS.IDF:ascii"]), 1)

    def test_short_memory_read_reports_less_than_planned(self):
        data = b"x" * 128
        scanner = load_scanner(data, stop_at=32)
        hits, scanned = scanner(Block(data), Refs())
        self.assertEqual(scanned, 32)
        self.assertEqual(hits, {})


if __name__ == "__main__":
    unittest.main()
