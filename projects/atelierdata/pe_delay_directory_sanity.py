"""Read-only PE32 delay-load directory sanity check for authorized static research.

No executable code is run, no proprietary content is exported, no DRM or IDF
format is interpreted. Public report contains structural aggregates only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import zipfile

MAX_PE = 64 * 1024 * 1024
MAX_DESCRIPTORS = 256
MAX_NAME = 128
ORIGINAL_MEMBER = 'Autodata__3.45/ADCDA2/ADBCD.exe'
ORIGINAL_PART = 'autodata_part_0001.zip'


def _u16(data, pos):
    if pos < 0 or pos + 2 > len(data):
        raise ValueError('PE field outside file')
    return struct.unpack_from('<H', data, pos)[0]


def _u32(data, pos):
    if pos < 0 or pos + 4 > len(data):
        raise ValueError('PE field outside file')
    return struct.unpack_from('<I', data, pos)[0]


def _entropy(data):
    if not data:
        return 0.0
    counts = Counter(data)
    return round(-sum((n / len(data)) * math.log2(n / len(data)) for n in counts.values()), 4)


def analyze(data: bytes, expected_sha256: str) -> dict:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(
            ch not in '0123456789abcdefABCDEF' for ch in expected_sha256):
        raise ValueError('Expected SHA256 must be 64 hex characters')
    if len(data) > MAX_PE or len(data) < 0x100 or data[:2] != b'MZ':
        raise ValueError('Invalid PE size or DOS header')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError('Original SHA256 mismatch')
    pe_at = _u32(data, 0x3c)
    if pe_at + 24 > len(data) or data[pe_at:pe_at + 4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    if _u16(data, pe_at + 4) != 0x14c:
        raise ValueError('Only PE32 x86 is supported')
    n_sections = _u16(data, pe_at + 6)
    optional_size = _u16(data, pe_at + 20)
    optional = pe_at + 24
    if (n_sections < 1 or n_sections > 96 or optional_size < 96 or
            optional + optional_size + 40 * n_sections > len(data) or
            _u16(data, optional) != 0x10b):
        raise ValueError('Invalid PE32 optional header or section table')
    image_base = _u32(data, optional + 28)
    header_size = _u32(data, optional + 60)
    section_table = optional + optional_size
    sections = []
    for index in range(n_sections):
        at = section_table + index * 40
        virtual_address = _u32(data, at + 12)
        raw_size = _u32(data, at + 16)
        raw_offset = _u32(data, at + 20)
        if raw_size and (raw_offset > len(data) or raw_size > len(data) - raw_offset):
            raise ValueError('PE section raw data outside file')
        sections.append((virtual_address, raw_size, raw_offset))

    def map_rva(rva: int, length: int = 1) -> int:
        if rva < 0 or length < 1 or rva + length > 0x100000000:
            raise ValueError('Invalid RVA')
        matches = [raw + rva - va for va, size, raw in sections
                   if size and va <= rva and rva + length <= va + size]
        if len(matches) > 1:
            raise ValueError('Ambiguous PE section RVA')
        if matches:
            return matches[0]
        if rva + length <= min(header_size, len(data)):
            return rva
        raise ValueError('Unmapped PE RVA')

    directory_count = _u32(data, optional + 92)
    delay_at = optional + 96 + 13 * 8
    if directory_count <= 13 or delay_at + 8 > optional + optional_size:
        delay_rva = delay_size = 0
    else:
        delay_rva, delay_size = struct.unpack_from('<II', data, delay_at)
    report = {
        'schema': 'atelierdata-delay-directory-sanity-v1',
        'sha256': digest,
        'pe_format': 'PE32 x86',
        'delay_directory_declared': bool(delay_rva or delay_size),
        'directory_size_bytes': delay_size,
        'directory_entropy_bits_per_byte': None,
        'complete_descriptor_slots': 0,
        'nonzero_descriptor_slots': 0,
        'invalid_attribute_slots': 0,
        'plausible_name_descriptors': 0,
        'zero_terminator_found': False,
        'trailing_bytes_after_slots': 0,
        'issues': [],
        'target_executed': False,
        'idf_decoder_proven': False,
        'license_checked': False,
    }
    issues = set()
    if not (delay_rva or delay_size):
        report['state'] = 'ABSENT'
        return report
    if not delay_rva or delay_size < 32 or delay_size > MAX_DESCRIPTORS * 32 + 32:
        issues.add('INVALID_DIRECTORY_DECLARATION')
    else:
        try:
            # Only the declared bytes are read. Mapping must not cross a section.
            offset = map_rva(delay_rva, delay_size)
        except ValueError:
            issues.add('UNMAPPED_DIRECTORY')
        else:
            blob = data[offset:offset + delay_size]
            report['directory_entropy_bits_per_byte'] = _entropy(blob)
            slots, remainder = divmod(len(blob), 32)
            report['complete_descriptor_slots'] = slots
            report['trailing_bytes_after_slots'] = remainder
            if remainder:
                issues.add('NON_DESCRIPTOR_TRAILING_BYTES')
            for index in range(min(slots, MAX_DESCRIPTORS)):
                fields = struct.unpack_from('<8I', blob, index * 32)
                if not any(fields):
                    report['zero_terminator_found'] = True
                    break
                report['nonzero_descriptor_slots'] += 1
                attributes, name_pointer = fields[:2]
                if attributes & ~1:
                    report['invalid_attribute_slots'] += 1
                    continue
                name_rva = name_pointer if attributes & 1 else name_pointer - image_base
                try:
                    name_offset = map_rva(name_rva)
                    name_end = data.find(b'\0', name_offset, min(len(data), name_offset + MAX_NAME + 1))
                    if name_end <= name_offset:
                        raise ValueError('Invalid DLL name')
                    raw = data[name_offset:name_end]
                    if any(ch < 32 or ch > 126 for ch in raw):
                        raise ValueError('Invalid DLL name')
                    report['plausible_name_descriptors'] += 1
                except ValueError:
                    issues.add('UNMAPPED_OR_INVALID_NAME')
            if report['invalid_attribute_slots']:
                issues.add('INVALID_DESCRIPTOR_ATTRIBUTES')
            if not report['zero_terminator_found']:
                issues.add('MISSING_ZERO_TERMINATOR')
            if slots > MAX_DESCRIPTORS:
                issues.add('DESCRIPTOR_LIMIT')
    report['issues'] = sorted(issues)
    report['state'] = 'STRUCTURALLY_PLAUSIBLE' if not issues else 'NOT_VALIDATED_AS_STANDARD_DELAY_IMPORTS'
    report['interpretation'] = ('The declared PE delay directory is metadata only. '
        'A malformed directory does not establish valid delay imports, a packer, '
        'a decoding algorithm, or runtime behavior.')
    return report


def analyze_zip(part: Path, expected_sha256: str) -> dict:
    part = Path(part)
    if part.name.lower() != ORIGINAL_PART:
        raise ValueError('Only the approved original part 0001 is accepted; blocked part 0016 is never opened')
    with zipfile.ZipFile(part) as archive:
        entries = [entry for entry in archive.infolist() if entry.filename == ORIGINAL_MEMBER]
        if len(entries) != 1 or entries[0].file_size > MAX_PE:
            raise ValueError('Original executable missing, duplicated, or oversized')
        with archive.open(entries[0]) as stream:
            data = stream.read(MAX_PE + 1)
    return analyze(data, expected_sha256)


def run(part: Path, expected_sha256: str, output: Path) -> dict:
    part, output = Path(part), Path(output)
    if part.resolve() == output.resolve():
        raise ValueError('Output cannot overwrite original archive')
    report = analyze_zip(part, expected_sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip-part-0001', required=True, type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.zip_part_0001, args.expected_sha256, args.output)
    print('PE_DELAY_DIRECTORY_SANITY=' + result['state'])


if __name__ == '__main__':
    main()
