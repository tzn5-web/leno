#@category AtelierData
# Ghidra headless Jython 2.7. Private static direct-call graph only.
# Args: <original-pe> <expected-sha256> <private-output.json>
# No original code execution, IDF parsing, license interaction or data export.
import hashlib
import json
import os
import re

MAX_PE_BYTES = 64 * 1024 * 1024
MAX_FUNCTIONS = 100000
MAX_INSTRUCTIONS = 1000000
MAX_EDGES = 200000


def checked_paths():
    args = getScriptArgs()
    if len(args) != 3:
        raise ValueError('Usage: original-pe expected-sha256 private-callgraph.json')
    source, expected, output = args
    if not re.match(r'^[0-9a-fA-F]{64}$', expected):
        raise ValueError('Expected SHA256 must be 64 hex characters')
    if os.path.islink(source) or os.path.islink(output):
        raise ValueError('Symlink input/output not permitted')
    source, output = os.path.realpath(source), os.path.realpath(output)
    if source == output or not os.path.isfile(source):
        raise ValueError('Original PE missing or output aliases input')
    if os.path.getsize(source) < 256 or os.path.getsize(source) > MAX_PE_BYTES:
        raise ValueError('Original PE outside size limit')
    if not os.path.isdir(os.path.dirname(output)):
        raise ValueError('Private output directory missing')
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with open(source, 'rb') as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            sha.update(chunk)
            md5.update(chunk)
    expected = expected.lower()
    if sha.hexdigest() != expected:
        raise ValueError('Original PE SHA256 mismatch')
    imported_sha = currentProgram.getExecutableSHA256()
    imported_md5 = currentProgram.getExecutableMD5()
    if not imported_sha or str(imported_sha).lower() != expected:
        raise ValueError('Ghidra imported PE SHA256 mismatch')
    if not imported_md5 or str(imported_md5).lower() != md5.hexdigest():
        raise ValueError('Ghidra imported PE MD5 mismatch')
    return expected, md5.hexdigest(), output


def collect():
    manager = currentProgram.getFunctionManager()
    listing = currentProgram.getListing()
    iterator = manager.getFunctions(True)
    edges = []
    functions = 0
    instructions = 0
    skipped_calls = 0
    truncated = False
    while iterator.hasNext():
        monitor.checkCanceled()
        if functions >= MAX_FUNCTIONS:
            truncated = True
            break
        fn = iterator.next()
        functions += 1
        # External functions have no local executable body to inspect.
        if fn.isExternal():
            continue
        body = listing.getInstructions(fn.getBody(), True)
        while body.hasNext():
            monitor.checkCanceled()
            if instructions >= MAX_INSTRUCTIONS or len(edges) >= MAX_EDGES:
                truncated = True
                break
            ins = body.next()
            instructions += 1
            for ref in ins.getReferencesFrom():
                if not ref.getReferenceType().isCall():
                    continue
                # Reject computed/conditional calls. A direct Ghidra edge is
                # still static evidence, not a reachable runtime call.
                if str(ref.getReferenceType()) != 'UNCONDITIONAL_CALL':
                    skipped_calls += 1
                    continue
                dest = ref.getToAddress()
                if dest.isExternalAddress():
                    skipped_calls += 1
                    continue
                target = manager.getFunctionAt(dest)
                if target is None or target.isExternal():
                    skipped_calls += 1
                    continue
                if len(edges) >= MAX_EDGES:
                    truncated = True
                    break
                edges.append({
                    'caller': str(fn.getEntryPoint()),
                    'callee': str(target.getEntryPoint()),
                    'site': str(ins.getAddress()),
                    'reference_type': 'UNCONDITIONAL_CALL'
                })
            if truncated:
                break
        if truncated:
            break
    return edges, functions, instructions, skipped_calls, truncated


def main():
    sha, md5, output = checked_paths()
    edges, functions, instructions, skipped, truncated = collect()
    report = {
        'schema': 'atelierdata-ghidra-direct-callgraph-v1',
        'source_sha256': sha,
        'source_md5': md5,
        'source_sha256_verified': True,
        'ghidra_import_sha256_verified': True,
        'ghidra_import_md5_verified': True,
        'target_executed': False,
        'idf_decoder_proven': False,
        'private_only': True,
        'functions_inspected': functions,
        'instructions_inspected': instructions,
        'non_direct_or_unresolved_calls_skipped': skipped,
        'coverage_truncated': truncated,
        'edges': edges,
        'limitations': ('Ghidra-recognized direct unconditional function calls only. '
                        'No proof of runtime reachability, dataflow, file access or IDF decoding.')
    }
    if os.path.islink(output):
        raise ValueError('Private output changed to symlink')
    with open(output, 'w') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    println('ATELIERDATA_DIRECT_CALLGRAPH_PRIVATE=WRITTEN edges=' + str(len(edges)))


main()
