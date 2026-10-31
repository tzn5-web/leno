"""Read-only x86 PE import-call evidence from trusted GNU objdump disassembly.

This is not Ghidra control-flow validation and not an IDF decoder. It does not
execute the target, extract proprietary resources, or inspect licensing logic.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

EXPECTED_ORIGINAL_SHA256 = 'a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4'


def pe_sections(data):
    if len(data) < 0x100 or data[:2] != b'MZ':
        raise ValueError('Not an MZ executable')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if pe > len(data)-24 or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid PE header')
    n = struct.unpack_from('<H', data, pe+6)[0]
    optional_size = struct.unpack_from('<H', data, pe+20)[0]
    opt = pe+24
    if optional_size < 96 or opt+optional_size > len(data):
        raise ValueError('Invalid optional header')
    if struct.unpack_from('<H', data, opt)[0] != 0x10b:
        raise ValueError('Requires x86 PE32')
    image_base = struct.unpack_from('<I', data, opt+28)[0]
    sections = []
    table = opt+optional_size
    if n > 96 or table+n*40 > len(data):
        raise ValueError('Invalid section table')
    for index in range(n):
        start = table+40*index
        name = data[start:start+8].rstrip(b'\0').decode('ascii', errors='replace')
        virtual_size, rva, raw_size, raw_offset = struct.unpack_from('<IIII', data, start+8)
        flags = struct.unpack_from('<I', data, start+36)[0]
        if raw_size and raw_offset+raw_size > len(data):
            raise ValueError('Section exceeds file')
        if flags & 0x20000000 and raw_size:
            sections.append((name, image_base+rva, data[raw_offset:raw_offset+raw_size]))
    return image_base, sections


def parse_imports(text, image_base):
    imports = {}
    dll = None
    for line in text.splitlines():
        match = re.search(r'^\s*DLL Name:\s*(\S+)', line)
        if match:
            dll = match.group(1)
            continue
        match = re.match(r'^\s*([0-9a-fA-F]{8})\s+<none>\s+[0-9a-fA-F]{4}\s+(\S+)', line)
        if match and dll:
            imports[image_base+int(match.group(1),16)] = (dll, match.group(2))
    return imports


def raw_candidates(sections, imports):
    rows = []
    for section, base, blob in sections:
        for index in range(len(blob)-5):
            if blob[index] != 0xff or blob[index+1] not in (0x15, 0x25):
                continue
            target = struct.unpack_from('<I', blob, index+2)[0]
            if target in imports:
                rows.append((section, base+index, 'call' if blob[index+1] == 0x15 else 'jmp', target))
    return rows


def parse_disassembly(text, imports):
    results = []
    section = ''
    for line in text.splitlines():
        heading = re.match(r'^Disassembly of section (.+):$', line)
        if heading:
            section = heading.group(1)
            continue
        match = re.match(r'^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s+)+)\s*(call|jmp)\s+(.+)$', line)
        if not match:
            continue
        address = int(match.group(1),16)
        byte_text = match.group(2).split()
        if len(byte_text) != 6 or byte_text[:2] not in (['ff','15'], ['ff','25']):
            continue
        target = int.from_bytes(bytes.fromhex(''.join(byte_text[2:6])), 'little')
        if target in imports:
            results.append((section, address, match.group(3), target))
    return results


def analyze(path, expected_sha256=EXPECTED_ORIGINAL_SHA256, objdump='objdump'):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Refuse missing/symlink target')
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise ValueError('SHA256 mismatch: target not verified')
    image_base, sections = pe_sections(data)
    def run(*args):
        return subprocess.run([objdump,*args,str(path)],check=True,capture_output=True,
                              text=True,errors='replace',timeout=90).stdout
    imports = parse_imports(run('-p'), image_base)
    if not imports:
        raise ValueError('No parsed PE imports')
    raw = raw_candidates(sections, imports)
    aligned = parse_disassembly(run('-d','-M','intel'), imports)
    raw_set = set(raw)
    matched = [row for row in aligned if row in raw_set]
    grouped = collections.Counter(f'{imports[r[3]][0]}!{imports[r[3]][1]}' for r in matched)
    by_section = collections.Counter(row[0] for row in matched)
    summary = {
        'schema': 'atelierdata-pe-import-call-linear-audit-v1',
        'original_sha256': digest,
        'original_sha256_verified': True,
        'target_executed': False,
        'tool': 'GNU objdump linear disassembly, not Ghidra CFG',
        'pe32_image_base': f'0x{image_base:08x}',
        'static_imports': len(imports),
        'executable_sections': len(sections),
        'raw_ff15_ff25_candidates': len(raw),
        'linear_sweep_import_calls': len(matched),
        'not_aligned_in_linear_sweep': len(raw)-len(matched),
        'matched_import_names': dict(sorted(grouped.items())),
        'matched_sections': dict(sorted(by_section.items())),
        'idf_loader_proven': False,
        'note': 'Linear sweep can disassemble data as code; instruction alignment does not establish reachability.'
    }
    return summary


def self_test():
    text = 'DLL Name: KERNEL32.dll\n\t00e4401c  <none>  01c2  LoadLibraryA\n'
    imports = parse_imports(text, 0x400000)
    assert imports[0x124401c] == ('KERNEL32.dll','LoadLibraryA')
    blob = b'\x90\xff\x15\x1c\x40\x24\x01\x90'
    raw = raw_candidates([('TEST',0x401000,blob)],imports)
    assert raw == [('TEST',0x401001,'call',0x124401c)]
    sample = 'Disassembly of section TEST:\n  401001:\tff 15 1c 40 24 01 \tcall   DWORD PTR ds:0x124401c\n'
    assert parse_disassembly(sample,imports) == raw
    assert parse_disassembly(sample.replace('ff 15','90 15'),imports) == []
    try:
        pe_sections(b'MZ')
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid PE accepted')
    print('PE_STATIC_CALL_ALIGNMENT_SELF_TEST=PASS')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pe', type=Path)
    p.add_argument('--expected-sha256', default=EXPECTED_ORIGINAL_SHA256)
    p.add_argument('--objdump', default='objdump')
    p.add_argument('--output', type=Path)
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    if args.pe is None:
        p.error('--pe required')
    result = analyze(args.pe, args.expected_sha256, args.objdump)
    payload = json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.write_text(payload,encoding='utf-8')
    print(payload)


if __name__ == '__main__':
    main()
