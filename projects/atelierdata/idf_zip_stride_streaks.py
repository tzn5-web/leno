"""SHA256-gated, read-only IDF fixed-stride candidate audit.

Scans at most the first 2 MiB of each .IDF, but streams every selected
member to EOF for ZIP CRC checking. Public output contains only aggregates.
A repeated 8-byte token is not evidence of a record format or decoder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from array import array
from pathlib import Path

STRIDES = (17, 19, 21)
TOKEN = 8
MIN_RUN = 32
SCAN_LIMIT = 2 * 1024 * 1024
MAX_ZIP = 1024 ** 3
MAX_MEMBER = 128 * 1024 ** 2
MAX_TOTAL = 1024 ** 3


def longest_streak(data: bytes, stride: int) -> tuple[int, int]:
    """Return (any-token, >=3-distinct-byte token) consecutive run maxima."""
    if stride < TOKEN or len(data) < TOKEN + stride:
        return 0, 0
    n = len(data)
    # The count is saturated: report lower bounds, not exact record counts.
    runs = array('H', [1]) * n
    longest = diverse = 0
    for i in range(n - stride - TOKEN, -1, -1):
        if data[i:i + TOKEN] == data[i + stride:i + stride + TOKEN]:
            runs[i] = min(65535, 1 + runs[i + stride])
            if runs[i] > longest:
                longest = runs[i]
            if runs[i] > diverse and len(set(data[i:i + TOKEN])) >= 3:
                diverse = runs[i]
    return longest, diverse


def audit(archive_path: Path, expected_sha256: str) -> dict:
    archive_path = Path(archive_path)
    if 'part_0016' in archive_path.name.casefold():
        raise ValueError('Blocked part_0016 refused')
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError('Archive missing or symlink')
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('Lowercase expected SHA256 required')
    if archive_path.stat().st_size > MAX_ZIP:
        raise ValueError('ZIP size limit exceeded')
    h = hashlib.sha256()
    with archive_path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    if h.hexdigest() != expected_sha256:
        raise ValueError('ZIP SHA256 mismatch')

    total = count = 0
    hits = {str(s): 0 for s in STRIDES}
    diverse_hits = {str(s): 0 for s in STRIDES}
    seen = set()
    with zipfile.ZipFile(archive_path) as archive:
        # Validate *all* selected entries before consuming any member.
        selected = []
        for member in archive.infolist():
            if member.is_dir() or not member.filename.casefold().endswith('.idf'):
                continue
            path = member.filename.replace('\\', '/')
            parts = path.split('/')
            if (path.startswith('/') or any(p in ('', '.', '..') for p in parts)
                    or ':' in parts[0]):
                raise ValueError('Unsafe ZIP member path')
            if path.casefold() in seen:
                raise ValueError('Duplicate IDF member')
            seen.add(path.casefold())
            if stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError('ZIP symlink refused')
            if member.file_size > MAX_MEMBER or total + member.file_size > MAX_TOTAL:
                raise ValueError('IDF member/total size limit')
            total += member.file_size
            selected.append(member)
        for member in selected:
            sample = bytearray()
            consumed = 0
            with archive.open(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    if len(sample) < SCAN_LIMIT:
                        sample.extend(block[:SCAN_LIMIT - len(sample)])
                    consumed += len(block)
            if consumed != member.file_size:
                raise ValueError('Incomplete IDF ZIP member')
            count += 1
            data = bytes(sample)
            for stride in STRIDES:
                any_run, diverse_run = longest_streak(data, stride)
                hits[str(stride)] += int(any_run >= MIN_RUN)
                diverse_hits[str(stride)] += int(diverse_run >= MIN_RUN)
    return {
        'schema': 'atelierdata-idf-zip-stride-streaks-v1',
        'archive_sha256_verified': True,
        'idf_files_crc_checked': count,
        'idf_bytes_crc_checked': total,
        'scan_limit_bytes_per_idf': SCAN_LIMIT,
        'stride_candidates': list(STRIDES),
        'token_width_bytes': TOKEN,
        'minimum_consecutive_occurrences': MIN_RUN,
        'files_with_32_repeated_tokens_by_stride': hits,
        'files_with_32_diverse_repeated_tokens_by_stride': diverse_hits,
        'original_executed': False,
        'idf_decoder_proven': False,
        'limitations': ('First 2 MiB per IDF only. Exact byte repetition is not proof '
                        'of field boundaries, record widths, compression, encryption or a decoder.'),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', required=True, type=Path)
    parser.add_argument('--expected-zip-sha256', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.zip, args.expected_zip_sha256)
    rendered = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        if args.output.is_symlink() or args.output.resolve() == args.zip.resolve():
            parser.error('Output must not alias original ZIP')
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()
