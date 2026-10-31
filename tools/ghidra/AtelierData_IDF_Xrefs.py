#@category AtelierData
# Ghidra headless Jython script. Static evidence only; does not run target code.
# Use only with binaries for which the analyst has legal analysis rights.
import json
import hashlib
from jarray import zeros

TERMS = ('MODELS.IDF', 'CONST.IDF', 'CSS.IDF', 'DTC.IDF', '.IDF',
         'inflate 1.2.3', 'TFRMAUTODATABASE', 'ChilkatCrypt2')
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
                            xrefs.append(str(ref.getFromAddress()))
                        entries.append({'address': str(addr), 'references_from': xrefs})
                    at = idx + 1
        carry = data[-overlap:]
        offset += count
    return {key: val for key, val in found.items() if val}


def main():
    args = getScriptArgs()
    if not args or not args[0]:
        raise ValueError('Provide a private local JSON report path as the first script argument')
    destination = args[0]
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
