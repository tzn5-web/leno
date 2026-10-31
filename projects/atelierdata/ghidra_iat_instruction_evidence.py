"""Verify private Ghidra IAT instruction evidence against an authorized PE32.

Read-only. A Ghidra 'recognized' instruction is evidence of disassembly,
not evidence of reachability, a file loader, a decoder or licensing status.
The public output contains counts only. No proprietary bytes are exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

SCHEMA = 'atelierdata-ghidra-iat-evidence-public-v1'
PRIVATE_IAT_SCHEMA = 'atelierdata-pe-iat-private-v1'
GHIDRA_SCHEMA = 'atelierdata-ghidra-iat-instruction-check-v1'
MAX_PE = 64 * 1024 * 1024
MAX_JSON = 32 * 1024 * 1024
MAX_CANDIDATES = 200000
HEX_ADDRESS = re.compile(r'(?:0x)?[0-9a-fA-F]{1,8}\Z')
HEX_SHA = re.compile(r'[0-9a-fA-F]{64}\Z')


def _u16(data: bytes, at: int) -> int:
    if at < 0 or at + 2 > len(data):
        raise ValueError('Truncated PE16')
    return struct.unpack_from('<H', data, at)[0]


def _u32(data: bytes, at: int) -> int:
    if at < 0 or at + 4 > len(data):
        raise ValueError('Truncated PE32')
    return struct.unpack_from('<I', data, at)[0]


def _layout(data: bytes) -> tuple[int, list[tuple[int, int, int, int, bool]]]:
    if not (256 <= len(data) <= MAX_PE) or data[:2] != b'MZ':
        raise ValueError('Invalid bounded MZ')
    pe = _u32(data, 0x3c)
    if pe < 64 or pe + 24 > len(data) or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    if _u16(data, pe+4) != 0x14c:
        raise ValueError('Expected x86 PE')
    count = _u16(data, pe+6)
    optional = _u16(data, pe+20)
    start = pe+24
    if not (1 <= count <= 96) or optional < 96 or start+optional+count*40 > len(data):
        raise ValueError('Invalid section table')
    if _u16(data, start) != 0x10b:
        raise ValueError('Expected PE32')
    base = _u32(data, start+28)
    sections = []
    for i in range(count):
        off = start+optional+i*40
        rva, raw_size, raw_at = (_u32(data, off+x) for x in (12, 16, 20))
        flags = _u32(data, off+36)
        if raw_size and (raw_at > len(data) or raw_size > len(data)-raw_at):
            raise ValueError('Section outside PE')
        sections.append((rva, raw_size, raw_at, base, bool(flags & 0x20000000)))
    return base, sections


def _int32(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError('Invalid 32-bit integer')
    return value


def _address(value: object) -> int:
    if not isinstance(value, str) or not HEX_ADDRESS.fullmatch(value):
        raise ValueError('Invalid Ghidra address')
    return int(value, 16)


def _mapped(data: bytes, sections: list, va: int) -> int:
    matches = []
    for rva, size, offset, base, executable in sections:
        start = base + rva
        if executable and start <= va and va+6 <= start+size:
            matches.append(offset+va-start)
    if len(matches) != 1:
        raise ValueError('Candidate has ambiguous or absent executable mapping')
    result = matches[0]
    if result+6 > len(data):
        raise ValueError('Candidate extends beyond PE')
    return result


def _rows(value: object) -> list:
    if not isinstance(value, list) or len(value) > MAX_CANDIDATES:
        raise ValueError('Missing/excessive candidates')
    return value


def verify(data: bytes, expected_sha: str, iat: dict, ghidra: dict) -> dict:
    if not isinstance(expected_sha, str) or not HEX_SHA.fullmatch(expected_sha):
        raise ValueError('Expected SHA256 is mandatory')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha.lower():
        raise ValueError('Original SHA256 mismatch')
    if not isinstance(iat, dict) or iat.get('schema') != PRIVATE_IAT_SCHEMA or iat.get('sha256') != digest:
        raise ValueError('Private IAT report mismatch')
    if not isinstance(ghidra, dict) or ghidra.get('schema') != GHIDRA_SCHEMA or ghidra.get('source_sha256') != digest:
        raise ValueError('Ghidra report mismatch')
    _, sections = _layout(data)
    original, checks = _rows(iat.get('candidates')), _rows(ghidra.get('candidates'))
    if len(original) != len(checks) or type(ghidra.get('candidate_count')) is not int or ghidra['candidate_count'] != len(checks):
        raise ValueError('Candidate count mismatch')
    if not isinstance(ghidra.get('program_name'), str) or not ghidra['program_name']:
        raise ValueError('Missing program identity label')
    seen = set()
    recognized = references = 0
    kinds = {'call': 0, 'jump': 0}
    for source, result in zip(original, checks):
        if not isinstance(source, dict) or not isinstance(result, dict):
            raise ValueError('Malformed candidate')
        va = _int32(source.get('instruction_va'))
        file_offset = _int32(source.get('file_offset'))
        target = _int32(source.get('iat_va'))
        kind = source.get('kind')
        if kind not in kinds or not isinstance(source.get('symbol'), str) or not source['symbol']:
            raise ValueError('Malformed private IAT candidate')
        if va in seen:
            raise ValueError('Duplicate candidate address')
        seen.add(va)
        if _address(result.get('address')) != va or result.get('symbol') != source['symbol']:
            raise ValueError('Ghidra candidate identity mismatch')
        mapped = _mapped(data, sections, va)
        if file_offset != mapped:
            raise ValueError('Private IAT file offset mismatch')
        expected = b'\xff' + (b'\x15' if kind == 'call' else b'\x25') + struct.pack('<I', target)
        if data[mapped:mapped+6] != expected:
            raise ValueError('IAT instruction bytes mismatch')
        if type(result.get('recognized_instruction')) is not bool or type(result.get('in_memory')) is not bool:
            raise ValueError('Missing Ghidra instruction booleans')
        ref_count = result.get('references_from_instruction')
        if type(ref_count) is not int or not 0 <= ref_count <= MAX_CANDIDATES:
            raise ValueError('Invalid reference count')
        if result['recognized_instruction']:
            if not result['in_memory'] or str(result.get('mnemonic', '')).upper() != ('CALL' if kind == 'call' else 'JMP'):
                raise ValueError('Contradictory recognized instruction')
            recognized += 1
            kinds[kind] += 1
        if result.get('mnemonic') is not None and ref_count:
            references += 1
    if (type(ghidra.get('recognized_instruction_count')) is not int or
        ghidra['recognized_instruction_count'] != recognized or
        type(ghidra.get('instructions_with_references')) is not int or
        ghidra['instructions_with_references'] != references):
        raise ValueError('Ghidra summary counts mismatch')
    return {
        'schema': SCHEMA,
        'original_sha256_verified': True,
        'private_iat_report_bound_to_pe_sha256': True,
        'ghidra_report_bound_to_pe_sha256_field': True,
        'ghidra_imported_program_identity_independently_verified': False,
        'raw_iat_candidate_bytes_verified': len(original),
        'ghidra_recognized_instructions_reported': recognized,
        'ghidra_unrecognized_candidates': len(original)-recognized,
        'recognized_calls': kinds['call'],
        'recognized_jumps': kinds['jump'],
        'reported_instructions_with_references': references,
        'target_executed': False,
        'idf_loader_proven': False,
        'idf_decoder_proven': False,
        'limitations': 'Raw bytes and report consistency verified. Ghidra program identity and its actual disassembly are not independently attested; recognized instructions do not establish reachability or IDF decoding.'
    }


def _json(path: Path) -> dict:
    with path.open('rb') as stream:
        data = stream.read(MAX_JSON+1)
    if len(data) > MAX_JSON:
        raise ValueError('Oversized evidence JSON')
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise ValueError('Expected JSON object')
    return obj


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pe', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--private-iat', type=Path, required=True)
    p.add_argument('--private-ghidra', type=Path, required=True)
    p.add_argument('--public-output', type=Path)
    args = p.parse_args()
    inputs = (args.pe, args.private_iat, args.private_ghidra)
    if args.public_output and args.public_output.resolve() in {x.resolve() for x in inputs}:
        p.error('Public output may not overwrite private evidence')
    try:
        with args.pe.open('rb') as stream:
            data = stream.read(MAX_PE+1)
        report = verify(data, args.expected_sha256, _json(args.private_iat), _json(args.private_ghidra))
        encoded = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if args.public_output:
            args.public_output.parent.mkdir(parents=True, exist_ok=True)
            args.public_output.write_text(encoded, encoding='utf-8')
        print(encoded, end='')
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError) as exc:
        print(json.dumps({'schema': SCHEMA, 'status': 'FAIL', 'error_type': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
