"""Bounded static PE32 import/IAT callsite triage for authorized interoperability.

Never executes a target or interprets encrypted/proprietary data. FF 15/FF 25
byte matches are *candidates*, not disassembled instructions or proof of flow.
Public JSON contains only aggregate counts; optional private JSON has offsets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

MAX_PE = 64 * 1024 * 1024
MAX_SECTIONS = 96
MAX_IMPORTS = 8192
MAX_CANDIDATES = 200000
LITERAL_PROBES = ('CreateFileA', 'CreateFileW', 'ReadFile', 'SetFilePointer',
                  'GetProcAddress', 'LoadLibraryA', 'SentinelKeyW.DLL',
                  'inflate 1.2.3', 'TFRMAUTODATABASE', '.IDF')
FOCUS = ('createfile', 'readfile', 'setfilepointer', 'getfilesize', 'getfiletype',
         'closehandle', 'getfileattributes', 'findfirstfile', 'findnextfile',
         'loadlibrary', 'getprocaddress', 'mapviewoffile', 'createfilemapping',
         'virtualalloc', 'virtualprotect', 'rtl', 'crypt', 'inflate', 'uncompress')


def _u16(data, at):
    if at < 0 or at + 2 > len(data):
        raise ValueError('PE field outside file')
    return struct.unpack_from('<H', data, at)[0]


def _u32(data, at):
    if at < 0 or at + 4 > len(data):
        raise ValueError('PE field outside file')
    return struct.unpack_from('<I', data, at)[0]


def _cstring(data, at, max_length=256):
    if at < 0 or at >= len(data):
        raise ValueError('String address outside file')
    end = data.find(b'\0', at, min(len(data), at + max_length + 1))
    if end < 0:
        raise ValueError('Unterminated PE import name')
    return data[at:end].decode('ascii', errors='replace')


def parse_pe32(data):
    if len(data) < 256 or len(data) > MAX_PE or data[:2] != b'MZ':
        raise ValueError('Not a bounded MZ file')
    pe = _u32(data, 0x3c)
    if pe < 64 or pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    if _u16(data, pe + 4) != 0x14c:
        raise ValueError('Only x86 PE32 supported')
    count = _u16(data, pe + 6)
    if count < 1 or count > MAX_SECTIONS:
        raise ValueError('Invalid section count')
    opt_size = _u16(data, pe + 20)
    opt = pe + 24
    if opt_size < 104 or opt + opt_size > len(data) or _u16(data, opt) != 0x10b:
        raise ValueError('Invalid PE32 optional header')
    image_base = _u32(data, opt + 28)
    header_size = _u32(data, opt + 60)
    n_dirs = _u32(data, opt + 92)
    if n_dirs < 2 or opt_size < 112:
        raise ValueError('No import data directory')
    imp_rva, imp_size = _u32(data, opt + 104), _u32(data, opt + 108)
    sec_start = opt + opt_size
    sections = []
    for i in range(count):
        off = sec_start + 40 * i
        if off + 40 > len(data):
            raise ValueError('Truncated section headers')
        name = data[off:off + 8].split(b'\0', 1)[0].decode('ascii', errors='replace')
        vsize, rva, raw_size, raw_at = (_u32(data, off + x) for x in (8, 12, 16, 20))
        flags = _u32(data, off + 36)
        if raw_size and (raw_at > len(data) or raw_size > len(data) - raw_at):
            raise ValueError('Section outside file')
        sections.append(dict(name=name, rva=rva, vsize=vsize, raw_size=raw_size,
                             raw_at=raw_at, executable=bool(flags & 0x20000000)))

    def rva_offset(rva, need=1):
        for s in sections:
            if s['rva'] <= rva and rva - s['rva'] + need <= s['raw_size']:
                return s['raw_at'] + rva - s['rva']
        if rva + need <= min(len(data), header_size):
            return rva
        raise ValueError('RVA not mapped to file bytes')

    imports = {}
    if imp_rva and imp_size:
        desc = rva_offset(imp_rva, 20)
        for idx in range(min(MAX_IMPORTS, imp_size // 20 + 1)):
            at = desc + idx * 20
            original, timestamp, forward, name_rva, first = (_u32(data, at + x) for x in (0, 4, 8, 12, 16))
            if not any((original, timestamp, forward, name_rva, first)):
                break
            if not name_rva or not first:
                raise ValueError('Malformed import descriptor')
            dll = _cstring(data, rva_offset(name_rva))
            thunk_rva = original or first
            for n in range(MAX_IMPORTS):
                thunk = _u32(data, rva_offset(thunk_rva + n * 4, 4))
                if thunk == 0:
                    break
                if thunk & 0x80000000:
                    symbol = f'#{thunk & 0xffff}'
                else:
                    symbol = _cstring(data, rva_offset(thunk + 2))
                iat_va = image_base + first + n * 4
                if iat_va > 0xffffffff:
                    raise ValueError('IAT address overflows PE32')
                imports[iat_va] = dict(dll=dll, symbol=symbol, iat_rva=first + n * 4)
            else:
                raise ValueError('Excessive imported functions')
        else:
            raise ValueError('Excessive import descriptors')
    return dict(sections=sections, imports=imports, image_base=image_base)


def analyze(data, expected_sha):
    if len(expected_sha) != 64 or any(c not in '0123456789abcdefABCDEF' for c in expected_sha):
        raise ValueError('Expected SHA256 is mandatory')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha.lower():
        raise ValueError('Original SHA256 mismatch')
    pe = parse_pe32(data)
    counts = Counter()
    private = []
    scanned = 0
    for sec in pe['sections']:
        if not sec['executable'] or not sec['raw_size']:
            continue
        raw = data[sec['raw_at']:sec['raw_at'] + sec['raw_size']]
        scanned += len(raw)
        # FF 15 / FF 25 + 32-bit absolute address, commonly used for IAT calls/jumps.
        # This is a raw-byte triage only; instruction boundaries are unverified.
        for i in range(len(raw) - 5):
            if raw[i] != 0xff or raw[i + 1] not in (0x15, 0x25):
                continue
            va = struct.unpack_from('<I', raw, i + 2)[0]
            item = pe['imports'].get(va)
            if item is None:
                continue
            kind = 'call' if raw[i + 1] == 0x15 else 'jump'
            key = f"{item['dll'].lower()}!{item['symbol']}:{kind}"
            counts[key] += 1
            if len(private) >= MAX_CANDIDATES:
                raise ValueError('Excessive raw IAT candidates')
            private.append(dict(section=sec['name'], file_offset=sec['raw_at'] + i,
                                instruction_va=pe['image_base'] + sec['rva'] + i,
                                imported_dll=item['dll'], symbol=item['symbol'], kind=kind, iat_va=va))
    # Count literal API names and exact absolute-address references. A raw pointer
    # occurrence is not a Ghidra code reference or a proven loader edge.
    literal_counts = {}
    private_literals = []
    for term in LITERAL_PROBES:
        variants = {}
        for encoding in ('ascii', 'utf-16le'):
            needle = term.encode(encoding)
            positions = []
            start = 0
            while len(positions) < 1024:
                at = data.find(needle, start)
                if at < 0:
                    break
                positions.append(at)
                start = at + 1
            pointer_candidates = 0
            for at in positions:
                for sec in pe['sections']:
                    if sec['raw_size'] and sec['raw_at'] <= at < sec['raw_at'] + sec['raw_size']:
                        va = pe['image_base'] + sec['rva'] + at - sec['raw_at']
                        if va <= 0xffffffff:
                            packed = struct.pack('<I', va)
                            pointer_candidates += sum(
                                data[s['raw_at']:s['raw_at'] + s['raw_size']].count(packed)
                                for s in pe['sections'] if s['executable'] and s['raw_size'])
                        break
            variants[encoding] = {'literal_count_at_most_1024': len(positions),
                                  'truncated': len(positions) == 1024,
                                  'raw_pointer_candidates_in_executable_sections': pointer_candidates}
            private_literals.append({'term': term, 'encoding': encoding, 'file_offsets': positions})
        literal_counts[term] = variants
    selected = {k: v for k, v in sorted(counts.items())
                if any(t in k.lower() for t in FOCUS)}
    public = dict(schema='atelierdata-pe-iat-triage-v1', sha256=digest,
                  file_bytes=len(data), format='PE32 x86',
                  executable_sections_scanned=sum(s['executable'] and s['raw_size'] > 0 for s in pe['sections']),
                  executable_bytes_scanned=scanned, imported_dlls=sorted({v['dll'] for v in pe['imports'].values()}),
                  imported_symbol_count=len(pe['imports']),
                  candidate_count=sum(counts.values()),
                  focus_candidates=selected, literal_probes=literal_counts,
                  target_executed=False, idf_decoder_proven=False,
                  method='Raw FF15/FF25 patterns matching PE import IAT VAs; no disassembly or control-flow validation',
                  limitations='Matches may be incidental bytes; zero matches does not exclude indirect calls, Delphi runtime wrappers, dynamic imports, or a data loader.')
    return public, dict(schema='atelierdata-pe-iat-private-v1', sha256=digest,
                         md5=hashlib.md5(data).hexdigest(), candidates=private, imported_symbols=list(pe['imports'].values()),
                         literal_locations=private_literals)


def run(pe_path, expected_sha, public_path, private_path=None):
    pe_path, public_path = Path(pe_path), Path(public_path)
    source = pe_path.resolve()
    destination = public_path.resolve()
    if destination == source:
        raise ValueError('Public output must differ from input PE')
    if private_path is not None and Path(private_path).resolve() in (source, destination):
        raise ValueError('Private output must differ from input PE and public output')
    with pe_path.open('rb') as stream:
        data = stream.read(MAX_PE + 1)
    public, private = analyze(data, expected_sha)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(public, indent=2), encoding='utf-8')
    if private_path is not None:
        private_path = Path(private_path)
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_text(json.dumps(private, indent=2), encoding='utf-8')
    return public


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pe', type=Path)
    p.add_argument('--expected-sha256')
    p.add_argument('--public-output', type=Path)
    p.add_argument('--private-output', type=Path)
    a = p.parse_args()
    if not all((a.pe, a.expected_sha256, a.public_output)):
        p.error('--pe --expected-sha256 --public-output required')
    result = run(a.pe, a.expected_sha256, a.public_output, a.private_output)
    print(f"PE_IAT_TRIAGE=PASS candidates={result['candidate_count']} imported_symbols={result['imported_symbol_count']}")


if __name__ == '__main__':
    main()
