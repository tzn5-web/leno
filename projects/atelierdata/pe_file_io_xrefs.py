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
from pe_literal_evidence import mapped_literal_positions

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
        # An RVA must map uniquely to initialized bytes in the PE image.
        # Raw alignment padding is not evidence of an imported name or thunk.
        if rva < 0 or need < 1 or rva + need > 0x100000000:
            raise ValueError('Invalid PE32 RVA extent')
        matches = []
        for section in sections:
            delta = rva - section['rva']
            backed = min(section['raw_size'], section['vsize'])
            if delta >= 0 and delta + need <= backed:
                matches.append(section['raw_at'] + delta)
        if len(matches) > 1:
            raise ValueError('Ambiguous overlapping PE sections')
        if matches:
            if rva + need <= min(len(data), header_size):
                raise ValueError('PE header and section RVA overlap')
            return matches[0]
        if rva + need <= min(len(data), header_size):
            return rva
        raise ValueError('RVA not mapped to initialized file bytes')

    def mapped_cstring(rva):
        # Require the entire name including NUL to remain in one mapped span.
        # A file-offset-only scan can silently cross into raw section padding.
        for length in range(1, 258):
            offset = rva_offset(rva, length)
            if data[offset + length - 1] == 0:
                return _cstring(data, offset)
        raise ValueError('Unterminated mapped PE import name')

    imports = {}
    if bool(imp_rva) != bool(imp_size):
        raise ValueError('Half-populated PE import directory')
    if imp_rva and imp_size:
        if imp_size < 40 or imp_size % 20:
            raise ValueError('Invalid PE import directory extent')
        for idx in range(min(MAX_IMPORTS, imp_size // 20)):
            at = rva_offset(imp_rva + idx * 20, 20)
            original, timestamp, forward, name_rva, first = (_u32(data, at + x) for x in (0, 4, 8, 12, 16))
            if not any((original, timestamp, forward, name_rva, first)):
                break
            if not name_rva or not first:
                raise ValueError('Malformed import descriptor')
            dll = mapped_cstring(name_rva)
            thunk_rva = original or first
            for n in range(MAX_IMPORTS):
                thunk = _u32(data, rva_offset(thunk_rva + n * 4, 4))
                if thunk == 0:
                    break
                if thunk & 0x80000000:
                    symbol = f'#{thunk & 0xffff}'
                else:
                    rva_offset(thunk, 2)  # IMAGE_IMPORT_BY_NAME hint
                    symbol = mapped_cstring(thunk + 2)
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
        backed = min(sec['raw_size'], sec['vsize'])
        raw = data[sec['raw_at']:sec['raw_at'] + backed]
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
            # A substring, unbacked section padding or a missing NUL is not
            # evidence of a complete API literal. Keep the raw locations private.
            positions, truncated = mapped_literal_positions(
                data, pe['sections'], term, encoding, limit=1024,
                allow_word_prefix=(term == '.IDF'),
                case_insensitive=(term == '.IDF'))
            pointer_candidates = 0
            for at, rva in positions:
                va = pe['image_base'] + rva
                if va > 0xffffffff:
                    continue
                packed = struct.pack('<I', va)
                pointer_candidates += sum(
                    data[s['raw_at']:s['raw_at'] + min(s['raw_size'], s['vsize'])].count(packed)
                    for s in pe['sections'] if s['executable'] and min(s['raw_size'], s['vsize']))
            variants[encoding] = {'literal_count_at_most_1024': len(positions),
                                  'truncated': truncated,
                                  'raw_pointer_candidates_in_executable_sections': pointer_candidates}
            private_literals.append({'term': term, 'encoding': encoding,
                                     'file_offsets': [at for at, _ in positions]})
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
                  literal_matching_policy='API: exact NUL-terminated non-embedded identifier; .IDF: ASCII-case-insensitive NUL-terminated suffix (filename prefixes permitted); all hits in unambiguous initialized PE sections',
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
