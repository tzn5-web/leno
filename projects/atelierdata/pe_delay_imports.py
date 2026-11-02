"""SHA256-gated, read-only PE32 delay-import metadata triage.

Never executes a target. Reports counts publicly and names/RVAs privately.
Delay imports do not prove API reachability or IDF format interpretation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from pe_file_io_xrefs import MAX_PE, parse_pe32

MAX_DESCRIPTORS = 256
MAX_IMPORTS_PER_DLL = 8192
MAX_IMPORTS_TOTAL = 16384


def _u32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise ValueError('PE field outside file')
    return struct.unpack_from('<I', data, offset)[0]


def parse_delay_imports(data):
    """Parse IMAGE_DELAYLOAD_DESCRIPTOR metadata, rejecting ambiguous extents."""
    pe = parse_pe32(data)
    pe_offset = _u32(data, 0x3c)
    optional = pe_offset + 24
    optional_size = struct.unpack_from('<H', data, pe_offset + 20)[0]
    directory_count = _u32(data, optional + 92)
    if directory_count < 14:
        return []
    if optional_size < 96 + 14 * 8:
        raise ValueError('Delay directory not contained in optional header')
    directory_rva = _u32(data, optional + 96 + 13 * 8)
    directory_size = _u32(data, optional + 96 + 13 * 8 + 4)
    if bool(directory_rva) != bool(directory_size):
        raise ValueError('Half-populated delay import directory')
    if not directory_rva:
        return []
    if directory_size < 64 or directory_size % 32 or directory_size // 32 > MAX_DESCRIPTORS + 1:
        raise ValueError('Invalid bounded delay directory size')

    sections = pe['sections']
    image_base = pe['image_base']
    header_size = _u32(data, optional + 60)

    def map_rva(rva, size):
        if not 0 <= rva <= 0xffffffff or not 1 <= size <= 0xffffffff or rva + size > 0x100000000:
            raise ValueError('Invalid delay RVA extent')
        matches = []
        for section in sections:
            delta = rva - section['rva']
            backed = min(section['raw_size'], section['vsize'])
            if delta >= 0 and delta + size <= backed:
                matches.append(section['raw_at'] + delta)
        if len(matches) > 1:
            raise ValueError('Ambiguous delay RVA mapping')
        if matches:
            if rva < header_size and rva + size <= header_size:
                raise ValueError('Delay RVA aliases PE headers')
            return matches[0]
        if rva + size <= min(header_size, len(data)):
            return rva
        raise ValueError('Unmapped or uninitialized delay RVA')

    def mapped_string(rva):
        # Increasing span enforces one file-backed section through the NUL.
        out = bytearray()
        for i in range(257):
            b = data[map_rva(rva, i + 1) + i]
            if b == 0:
                return out.decode('ascii', errors='replace')
            if i == 256:
                break
            out.append(b)
        raise ValueError('Unterminated delay import string')

    def to_rva(value, is_rva):
        if not value:
            return 0
        if is_rva:
            return value
        if value < image_base:
            raise ValueError('Delay VA below image base')
        return value - image_base

    # A slot may have only one import owner. Overlapping classic/delay IAT
    # ranges or repeated delay descriptors make attribution ambiguous.
    occupied_iat_rvas = {entry['iat_rva'] for entry in pe['imports'].values()}
    result = []
    count_total = 0
    terminated = False
    for index in range(directory_size // 32):
        at = map_rva(directory_rva + 32 * index, 32)
        attrs, dll, hmod, iat, names, bound, unload, timestamp = struct.unpack_from('<8I', data, at)
        if not any((attrs, dll, hmod, iat, names, bound, unload, timestamp)):
            # A null descriptor terminates the directory. Any later nonzero
            # descriptor bytes make the claimed directory extent ambiguous.
            for tail in range(index + 1, directory_size // 32):
                tail_at = map_rva(directory_rva + 32 * tail, 32)
                if any(data[tail_at:tail_at + 32]):
                    raise ValueError('Nonzero bytes after delay descriptor terminator')
            terminated = True
            break
        if attrs not in (0, 1):
            raise ValueError('Unknown delay descriptor attributes')
        if index >= MAX_DESCRIPTORS or not dll or not iat or not names:
            raise ValueError('Malformed or excessive delay descriptor')
        is_rva = bool(attrs & 1)
        dll_rva = to_rva(dll, is_rva)
        iat_rva = to_rva(iat, is_rva)
        names_rva = to_rva(names, is_rva)
        dll_name = mapped_string(dll_rva)
        if not dll_name:
            raise ValueError('Empty delay DLL name')
        entries = []
        for n in range(MAX_IMPORTS_PER_DLL + 1):
            if n == MAX_IMPORTS_PER_DLL:
                raise ValueError('Excessive delay import entries')
            thunk = _u32(data, map_rva(names_rva + n * 4, 4))
            map_rva(iat_rva + n * 4, 4)
            if thunk == 0:
                break
            slot_rva = iat_rva + n * 4
            if slot_rva in occupied_iat_rvas:
                raise ValueError('Ambiguous duplicate classic/delay IAT slot')
            occupied_iat_rvas.add(slot_rva)
            count_total += 1
            if count_total > MAX_IMPORTS_TOTAL:
                raise ValueError('Excessive total delay imports')
            if thunk & 0x80000000:
                # IMAGE_ORDINAL_FLAG32 leaves bits 16..30 reserved.
                # Silently masking them would misattribute malformed thunks.
                if thunk & 0x7fff0000:
                    raise ValueError('Delay ordinal thunk has nonzero reserved bits')
                symbol = f'#{thunk & 0xffff}'
                ordinal = True
            else:
                name_rva = to_rva(thunk, is_rva)
                map_rva(name_rva, 2)
                symbol = mapped_string(name_rva + 2)
                if not symbol:
                    raise ValueError('Empty delay import symbol')
                ordinal = False
            entries.append({'symbol': symbol, 'ordinal': ordinal, 'iat_rva': iat_rva + n * 4})
        result.append({'dll': dll_name, 'descriptor_rva': directory_rva + 32 * index,
                       'rva_based': is_rva, 'entries': entries})
    if not terminated:
        raise ValueError('Delay import descriptors missing terminator')
    return result


def analyze(data, expected_sha256):
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(
            c not in '0123456789abcdefABCDEF' for c in expected_sha256):
        raise ValueError('Expected SHA256 is mandatory')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError('Original SHA256 mismatch')
    entries = parse_delay_imports(data)
    symbols = [item for descriptor in entries for item in descriptor['entries']]
    public = {'schema': 'atelierdata-pe-delay-imports-v1', 'sha256': digest,
              'file_bytes': len(data), 'delay_descriptors': len(entries),
              'delay_symbols': len(symbols),
              'named_symbols': sum(not e['ordinal'] for e in symbols),
              'ordinal_symbols': sum(e['ordinal'] for e in symbols),
              'rva_descriptors': sum(d['rva_based'] for d in entries),
              'va_descriptors': sum(not d['rva_based'] for d in entries),
              'target_executed': False, 'idf_decoder_proven': False,
              'limitations': 'Delay import metadata only; no code reachability, dynamic API resolution or IDF format inferred.'}
    private = {'schema': 'atelierdata-pe-delay-imports-private-v1', 'sha256': digest,
               'source_md5': hashlib.md5(data).hexdigest(), 'descriptors': entries}
    return public, private


def run(source, expected_sha256, public_output, private_output=None):
    source, public_output = Path(source), Path(public_output)
    locations = [source.resolve(), public_output.resolve()]
    if private_output is not None:
        locations.append(Path(private_output).resolve())
    if len(set(locations)) != len(locations):
        raise ValueError('Input and output paths must differ')
    with source.open('rb') as handle:
        data = handle.read(MAX_PE + 1)
    if len(data) > MAX_PE:
        raise ValueError('PE exceeds static analysis size limit')
    public, private = analyze(data, expected_sha256)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    public_output.write_text(json.dumps(public, indent=2), encoding='utf-8')
    if private_output is not None:
        private_output = Path(private_output)
        private_output.parent.mkdir(parents=True, exist_ok=True)
        private_output.write_text(json.dumps(private, indent=2), encoding='utf-8')
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--public-output', type=Path, required=True)
    parser.add_argument('--private-output', type=Path)
    args = parser.parse_args()
    summary = run(args.pe, args.expected_sha256, args.public_output, args.private_output)
    print(f"DELAY_IMPORT_TRIAGE=PASS descriptors={summary['delay_descriptors']} symbols={summary['delay_symbols']}")


if __name__ == '__main__':
    main()
