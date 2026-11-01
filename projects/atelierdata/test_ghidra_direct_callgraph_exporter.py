"""Synthetic-only exercise of the Ghidra Jython callgraph collector contract."""
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / 'tools' / 'ghidra' / 'AtelierData_Direct_Callgraph.py'


class Iterator:
    def __init__(self, items):
        self.items = iter(items)
        self.next_item = None
        self.ready = False

    def hasNext(self):
        if not self.ready:
            try:
                self.next_item = next(self.items)
                self.ready = True
            except StopIteration:
                return False
        return True

    def next(self):
        if not self.hasNext():
            raise StopIteration
        self.ready = False
        return self.next_item


class Address:
    def __init__(self, value, external=False):
        self.value, self.external = value, external

    def isExternalAddress(self):
        return self.external

    def getOffset(self):
        return int(self.value, 16)

    def __str__(self):
        return self.value


class ReferenceType:
    def __init__(self, name):
        self.name = name

    def isCall(self):
        return 'CALL' in self.name

    def __str__(self):
        return self.name


class Reference:
    def __init__(self, kind, target):
        self.kind, self.target = ReferenceType(kind), target

    def getReferenceType(self):
        return self.kind

    def getToAddress(self):
        return self.target


class Instruction:
    def __init__(self, address, refs):
        self.address, self.refs = address, refs

    def getAddress(self):
        return self.address

    def getReferencesFrom(self):
        return self.refs

    def getMnemonicString(self):
        return 'CALL'

    def getLength(self):
        return 5

    def getBytes(self):
        # Synthetic x86 E8 rel32 from 0x401020 to 0x402000.
        return [0xe8, 0xdb, 0x0f, 0x00, 0x00]


class Function:
    def __init__(self, address):
        self.address = address

    def getEntryPoint(self):
        return self.address

    def getBody(self):
        return self.address

    def isExternal(self):
        return False


class Manager:
    def __init__(self, source, target):
        self.source, self.target = source, target

    def getFunctions(self, forward):
        return Iterator([self.source, self.target])

    def getFunctionAt(self, address):
        return self.target if str(address) == str(self.target.getEntryPoint()) else None


class Listing:
    def __init__(self, source, instructions):
        self.source, self.instructions = source, instructions

    def getInstructions(self, body, forward):
        return Iterator(self.instructions if body == self.source.getEntryPoint() else [])


class MemoryBlock:
    def isExecute(self):
        return True


class Memory:
    def getBlock(self, address):
        return MemoryBlock()


class Program:
    def __init__(self, manager, listing):
        self.manager, self.listing = manager, listing

    def getFunctionManager(self):
        return self.manager

    def getListing(self):
        return self.listing

    def getMemory(self):
        return Memory()


class Monitor:
    def checkCanceled(self):
        return None


class ExporterContractTests(unittest.TestCase):
    def test_direct_call_only_and_unresolved_excluded(self):
        source = Function(Address('00401000'))
        target = Function(Address('00402000'))
        instructions = [Instruction(Address('00401020'), [
            Reference('UNCONDITIONAL_CALL', target.getEntryPoint()),
            Reference('COMPUTED_CALL', target.getEntryPoint()),
            Reference('UNCONDITIONAL_CALL', Address('00409999')),
            Reference('DATA', target.getEntryPoint())])]
        namespace = {'currentProgram': Program(Manager(source, target), Listing(source, instructions)),
                     'monitor': Monitor()}
        script = SCRIPT.read_text(encoding='utf-8')
        self.assertIn('ghidra_import_sha256_verified', script)
        self.assertIn('ghidra_import_md5_verified', script)
        self.assertTrue(script.rstrip().endswith('main()'))
        exec(compile(script.rsplit('\nmain()', 1)[0], str(SCRIPT), 'exec'), namespace)
        edges, functions, instructions_count, skipped, truncated = namespace['collect']()
        self.assertEqual(functions, 2)
        self.assertEqual(instructions_count, 1)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]['caller'], '00401000')
        self.assertEqual(edges[0]['callee'], '00402000')
        self.assertEqual(skipped, 2)
        self.assertFalse(truncated)


if __name__ == '__main__':
    unittest.main()
