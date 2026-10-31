#@category AtelierData
# Ghidra headless Jython 2.7. Read-only imported API/symbol cross-reference triage.
# Output contains private addresses: keep in private Drive, never public GitHub.
import json
import re

API_NAMES = ('CreateFileA', 'CreateFileW', 'ReadFile', 'SetFilePointer',
             'SetFilePointerEx', 'GetFileSize', 'GetFileSizeEx',
             'CreateFileMappingA', 'CreateFileMappingW', 'MapViewOfFile',
             'LoadLibraryA', 'LoadLibraryW', 'GetProcAddress',
             'CloseHandle', 'FindFirstFileA', 'FindFirstFileW')
MAX_SYMBOLS_PER_NAME = 32
MAX_REFS_PER_SYMBOL = 256


def collect():
    table = currentProgram.getSymbolTable()
    manager = currentProgram.getReferenceManager()
    listing = currentProgram.getListing()
    functions = currentProgram.getFunctionManager()
    found = {}
    for name in API_NAMES:
        monitor.checkCanceled()
        symbols = []
        for symbol in table.getSymbols(name):
            if len(symbols) >= MAX_SYMBOLS_PER_NAME:
                break
            address = symbol.getAddress()
            # A matching name alone does not prove an imported API.
            refs = []
            for ref in manager.getReferencesTo(address):
                if len(refs) >= MAX_REFS_PER_SYMBOL:
                    break
                source = ref.getFromAddress()
                function = functions.getFunctionContaining(source)
                instruction = listing.getInstructionAt(source)
                refs.append({
                    'source_address': str(source),
                    'reference_type': str(ref.getReferenceType()),
                    'instruction_mnemonic': (str(instruction.getMnemonicString()) if instruction else None),
                    'function_entry': (str(function.getEntryPoint()) if function else None)
                })
            symbols.append({
                'address': str(address),
                'external_address': bool(address.isExternalAddress()),
                'symbol_type': str(symbol.getSymbolType()),
                'parent_namespace': str(symbol.getParentNamespace().getName()),
                'references': refs,
                'references_truncated': len(refs) == MAX_REFS_PER_SYMBOL
            })
        if symbols:
            found[name] = symbols
    return found


def main():
    args = getScriptArgs()
    if len(args) != 2 or not args[0] or not re.match(r'^[0-9a-fA-F]{64}$', args[1]):
        raise ValueError('Expected: private-report.json independently-verified-PE-SHA256')
    digest = currentProgram.getExecutableSHA256()
    if digest is None or digest.lower() != args[1].lower():
        raise ValueError('Imported executable SHA256 mismatch')
    result = {
        'schema': 'atelierdata-ghidra-file-api-xrefs-v1',
        'source_sha256': digest.lower(),
        'target_executed': False,
        'idf_decoder_proven': False,
        'api_symbols': collect(),
        'limitations': ('Ghidra symbol references and containing functions only. '
                        'IAT indirection, dynamically resolved APIs, and missed '
                        'references can make this incomplete. Shared function '
                        'references do not establish a file decoder.')
    }
    with open(args[0], 'w') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
    print('ATELIERDATA_PRIVATE_FILE_API_XREFS=' + args[0])


main()
