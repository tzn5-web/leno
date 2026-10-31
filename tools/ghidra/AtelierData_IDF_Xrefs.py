#@category AtelierData
# Ghidra headless Jython script. Static evidence only; does not run target code.
# Use only with binaries for which the analyst has legal analysis rights.
import json
import hashlib
import re
from jarray import zeros

TERMS = ('MODELS.IDF', 'CONST.IDF', 'CSS.IDF', 'DTC.IDF', '.IDF',
         'inflate 1.2.3', 'TFRMAUTODATABASE', 'ChilkatCrypt2',
         'CreateFileA', 'CreateFileW', 'ReadFile', 'SetFilePointer',
         'GetProcAddress', 'LoadLibraryA', 'LoadLibraryW',
         'pbvm90.dll', 'libjcc.dll')
MAX_SCAN_BYTES = 128 * 1024 * 1024
MAX_MATCHES_PER_TERM = 32
MAX_XREFS_PER_MATCH = 16


def scan_block(block, refs):
    size = int(min(block.getSize(), MAX_SCAN_BYTES))
    found = {}
    if not block.isInitialized() or size <= 0:
        return found
    # Chunked scan avoids memory spikes; overlap covers matches on boundaries.
    offset = 0
    overlap = 128
    carry = bytearray()
    while offset < size:
        monitor.checkCanceled()
        take = min(1024 * 1024, size - offset)
        buf = zeros(take, 'b')
        count = currentProgram.getMemory().getBytes(block.getStart().add(offset), buf)
        if count <= 0:
            break
        data = carry + bytearray((int(v) & 255 for v in buf[:count]))
        base = offset - len(carry)
        for term in TERMS:
            for mode in ('ascii', 'utf16le'):
                pattern = bytearray(term.encode('ascii' if mode == 'ascii' else 'utf-16le'))
                key = term + ':' + mode
                entries = found.setdefault(key, [])
                if len(entries) >= MAX_MATCHES_PER_TERM:
                    continue
                at = 0
                while len(entries) < MAX_MATCHES_PER_TERM:
                    idx = data.find(pattern, at)
                    if idx < 0:
                        break
                    pos = base + idx
                    # Do not count matches already wholly contained in the
                    # preceding chunk's overlap. Retain boundary-crossing hits.
                    if pos >= 0 and pos < size and pos + len(pattern) > offset:
                        addr = block.getStart().add(pos)
                        xrefs = []
                        for ref in refs.getReferencesTo(addr):
                            if len(xrefs) >= MAX_XREFS_PER_MATCH:
                                break
                            source = ref.getFromAddress()
                            function = getFunctionContaining(source)
                            xrefs.append({'source_address': str(source),
                                          'containing_function': (str(function.getName()) if function else None),
                                          'function_entry': (str(function.getEntryPoint()) if function else None)})
                        entries.append({'address': str(addr), 'references_from': xrefs})
                    at = idx + 1
        carry = data[-overlap:]
        offset += count
    return {key: val for key, val in found.items() if val}


def main():
    args = getScriptArgs()
    if len(args) != 2 or not args[0] or not re.match(r'^[0-9a-fA-F]{32}
    refs = currentProgram.getReferenceManager()
    blocks = []
    observations = {}
    for block in currentProgram.getMemory().getBlocks():
        if not block.isInitialized():
            continue
        blocks.append({'name': str(block.getName()),
                       'size': int(block.getSize()),
                       'scanned_bytes': int(min(block.getSize(), MAX_SCAN_BYTES))})
        found = scan_block(block, refs)
        if found:
            observations[str(block.getName())] = found
    result = {
        'tool': 'Ghidra static analysis, AtelierData_IDF_Xrefs.py',
        'program_name': str(currentProgram.getName()),
        'language_id': str(currentProgram.getLanguageID()),
        'source_md5': imported_md5.lower(),
        'ghidra_import_md5_verified': True,
        'keyword_hit_types': ['ascii', 'utf16le'],
        'executed_target_binary': False,
        'idf_decoder_proven': False,
        'blocks': blocks,
        'keyword_hits': observations,
        'limitations': ('Static API-name/IDF keyword hits and containing functions only. ' 
                        'A string reference is not an API invocation. No proof of IDF loader, '
                        'compression algorithm, decryption, or legal right to copy data.')
    }
    with open(destination, 'w') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    print('ATELIERDATA_GHIDRA_STATIC_REPORT=' + destination)


main()
, args[1]):
        raise ValueError('Expected: private-output.json independently-computed-PE-MD5')
    destination = args[0]
    expected_md5 = args[1].lower()
    imported_md5 = currentProgram.getExecutableMD5()
    if imported_md5 is None or imported_md5.lower() != expected_md5:
        raise ValueError('Ghidra imported PE MD5 differs from independently verified source')
    refs = currentProgram.getReferenceManager()
    blocks = []
    observations = {}
    for block in currentProgram.getMemory().getBlocks():
        if not block.isInitialized():
            continue
        blocks.append({'name': str(block.getName()),
                       'size': int(block.getSize()),
                       'scanned_bytes': int(min(block.getSize(), MAX_SCAN_BYTES))})
        found = scan_block(block, refs)
        if found:
            observations[str(block.getName())] = found
    result = {
        'tool': 'Ghidra static analysis, AtelierData_IDF_Xrefs.py',
        'program_name': str(currentProgram.getName()),
        'language_id': str(currentProgram.getLanguageID()),
        'executed_target_binary': False,
        'idf_decoder_proven': False,
        'blocks': blocks,
        'keyword_hits': observations,
        'limitations': ('Static keyword hits and xrefs only. No proof of IDF loader, '
                        'compression algorithm, decryption, or legal right to copy data.')
    }
    with open(destination, 'w') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    print('ATELIERDATA_GHIDRA_STATIC_REPORT=' + destination)


main()
