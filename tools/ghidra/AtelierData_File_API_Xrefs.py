#@category AtelierData
# Ghidra headless Jython 2.7: read-only API-symbol reference triage.
# Private report only. Never executes imported binaries or decodes .IDF.
# Args: <original-pe> <expected-sha256> <private-output.json>
import hashlib
import json
import os
import re

API_NAMES = (
    "CreateFileA", "CreateFileW", "ReadFile", "SetFilePointer",
    "SetFilePointerEx", "GetFileSize", "GetFileSizeEx", "CloseHandle",
    "GetFileAttributesA", "GetFileAttributesW", "FindFirstFileA",
    "FindFirstFileW", "FindNextFileA", "FindNextFileW",
    "CreateFileMappingA", "CreateFileMappingW", "MapViewOfFile",
    "GetProcAddress", "LoadLibraryA", "LoadLibraryW",
    "LoadLibraryExA", "LoadLibraryExW"
)
MAX_PE_BYTES = 64 * 1024 * 1024
MAX_SYMBOLS = 300000
MAX_REFS = 50000
MAX_REFS_PER_SYMBOL = 128


def checked_paths():
    args = getScriptArgs()
    if len(args) != 3:
        raise ValueError("Usage: original-pe expected-sha256 private-report.json")
    source, expected, output = args
    if not re.match(r"^[0-9a-fA-F]{64}$", expected):
        raise ValueError("Expected SHA256 must be 64 hex characters")
    expected = expected.lower()
    if os.path.islink(source) or os.path.islink(output):
        raise ValueError("Linked input or output paths are not permitted")
    source, output = os.path.realpath(source), os.path.realpath(output)
    if source == output or not os.path.isfile(source):
        raise ValueError("Original PE missing or output aliases input")
    if os.path.getsize(source) < 256 or os.path.getsize(source) > MAX_PE_BYTES:
        raise ValueError("Original PE outside size limit")
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with open(source, "rb") as stream:
        while True:
            block = stream.read(65536)
            if not block:
                break
            sha.update(block)
            md5.update(block)
    if sha.hexdigest() != expected:
        raise ValueError("Original PE SHA256 mismatch")
    imported_sha = currentProgram.getExecutableSHA256()
    imported_md5 = currentProgram.getExecutableMD5()
    if not imported_sha or imported_sha.lower() != expected:
        raise ValueError("Ghidra imported PE SHA256 mismatch")
    if not imported_md5 or imported_md5.lower() != md5.hexdigest():
        raise ValueError("Ghidra imported PE MD5 mismatch")
    if not os.path.isdir(os.path.dirname(output)):
        raise ValueError("Private output parent must exist")
    return expected, output


def canonical_api(symbol_name):
    # Imported symbols can have __imp_, leading underscores or stdcall @N.
    name = str(symbol_name)
    if name.startswith("__imp_"):
        name = name[6:]
    name = name.lstrip("_")
    name = re.sub(r"@[0-9]+$", "", name)
    return name if name in API_NAMES else None


def collect():
    symbols = currentProgram.getSymbolTable().getAllSymbols(False)
    refs = currentProgram.getReferenceManager()
    funcs = currentProgram.getFunctionManager()
    listing = currentProgram.getListing()
    found = {}
    scanned = 0
    recorded = 0
    truncated = False
    while symbols.hasNext():
        monitor.checkCanceled()
        scanned += 1
        if scanned > MAX_SYMBOLS:
            truncated = True
            break
        sym = symbols.next()
        api = canonical_api(sym.getName())
        if api is None:
            continue
        addr = sym.getAddress()
        row = {
            "address": str(addr), "original_symbol_name": str(sym.getName()),
            "external_address": bool(addr.isExternalAddress()),
            "symbol_type": str(sym.getSymbolType()),
            "references": [], "references_truncated": False
        }
        for ref in refs.getReferencesTo(addr):
            monitor.checkCanceled()
            if len(row["references"]) >= MAX_REFS_PER_SYMBOL or recorded >= MAX_REFS:
                row["references_truncated"] = True
                truncated = True
                break
            src = ref.getFromAddress()
            fn = funcs.getFunctionContaining(src)
            ins = listing.getInstructionContaining(src)
            row["references"].append({
                "source_address": str(src),
                "function_entry": str(fn.getEntryPoint()) if fn else None,
                "instruction_mnemonic": str(ins.getMnemonicString()).upper() if ins else None,
                "reference_type": str(ref.getReferenceType())
            })
            recorded += 1
        found.setdefault(api, []).append(row)
    return found, scanned, recorded, truncated


def main():
    expected, output = checked_paths()
    found, scanned, recorded, truncated = collect()
    report = {
        "schema": "atelierdata-ghidra-file-api-xrefs-v1",
        "source_sha256": expected,
        "ghidra_program_sha256_verified": True,
        "ghidra_program_md5_verified": True,
        "target_executed": False,
        "idf_decoder_proven": False,
        "private_only": True,
        "symbols_scanned": scanned,
        "symbol_scan_truncated": truncated,
        "references_recorded": recorded,
        "api_symbols": found,
        "limitations": "Existing Ghidra symbol references only; decorated names included. IAT indirection, dynamic resolution and reachability are not proven."
    }
    if os.path.islink(output):
        raise ValueError("Private output changed to symlink")
    with open(output, "w") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    println("ATELIERDATA_FILE_API_XREFS_PRIVATE=WRITTEN refs=" + str(recorded))


main()
