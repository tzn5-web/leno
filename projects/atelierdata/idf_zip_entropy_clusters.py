"""Static, read-only .IDF similarity audit of one owner-authorized ZIP.

Requires the SHA256 of the entire allowed ZIP. Does not decode IDF, execute
original code, print proprietary bytes, filenames, offsets or per-file hashes.
The aggregate cannot identify encryption, compression or a loader.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
import re
import stat
import zipfile
from pathlib import Path

MAX_ZIP = 1024 ** 3
MAX_MEMBER = 128 * 1024 ** 2
MAX_TOTAL = 1024 ** 3
WINDOW = 65536
SMALL = 4096


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = collections.Counter(data)
    return -sum((count / len(data)) * math.log2(count / len(data))
                for count in counts.values())


def common_prefix(a: bytes, b: bytes) -> int:
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                min(len(a), len(b)))


def audit(archive_path: Path, expected_sha256: str) -> dict:
    archive_path = Path(archive_path)
    if (archive_path.name.casefold() == 'autodata_part_0016.zip' or
            'part_0016' in archive_path.name.casefold()):
        raise ValueError('Blocked part_0016 must not be accessed')
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError('Archive missing or symlink')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected lowercase archive SHA256 required')
    if archive_path.stat().st_size > MAX_ZIP:
        raise ValueError('Archive exceeds limit')
    digest = hashlib.sha256()
    with archive_path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError('Archive SHA256 mismatch')
    samples = []
    total = 0
    seen = set()
    with zipfile.ZipFile(archive_path) as z:
        for member in z.infolist():
            if member.is_dir() or not member.filename.lower().endswith('.idf'):
                continue
            path = member.filename.replace('\\', '/')
            parts = path.split('/')
            if (path.startswith('/') or any(part in ('', '.', '..') for part in parts)
                    or ':' in parts[0]):
                raise ValueError('Unsafe ZIP member path')
            if path.casefold() in seen:
                raise ValueError('Duplicate IDF member')
            seen.add(path.casefold())
            mode = member.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise ValueError('Symlink ZIP member refused')
            if member.file_size > MAX_MEMBER or total + member.file_size > MAX_TOTAL:
                raise ValueError('IDF member or aggregate size limit')
            total += member.file_size
            # Bounded allocation; CRC is verified by zipfile while streaming
            # the complete member. Only small fixed-size windows are retained.
            head = bytearray()
            middle = bytearray()
            tail = bytearray()
            middle_at = max(0, (member.file_size - SMALL) // 2)
            position = 0
            with z.open(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    if len(head) < WINDOW:
                        head.extend(block[:WINDOW - len(head)])
                    start = max(position, middle_at)
                    end = min(position + len(block), middle_at + SMALL)
                    if start < end:
                        middle.extend(block[start - position:end - position])
                    tail.extend(block)
                    if len(tail) > SMALL:
                        del tail[:-SMALL]
                    position += len(block)
            if position != member.file_size:
                raise ValueError('Incomplete ZIP member')
            samples.append((bytes(head[:64]), entropy(bytes(head[:WINDOW])),
                            min(entropy(bytes(head[:SMALL])), entropy(bytes(middle)),
                                entropy(bytes(tail)))))
    pairs = [common_prefix(a[0], b[0]) for a, b in itertools.combinations(samples, 2)
             if len(a[0]) >= 16 and len(b[0]) >= 16 and a[0][:16] == b[0][:16]]
    return {
        'schema': 'atelierdata-idf-zip-entropy-clusters-v1',
        'archive_sha256_verified': True,
        'idf_files_checked': len(samples),
        'idf_total_bytes_checked': total,
        'files_first64k_entropy_ge_7_95': sum(x[1] >= 7.95 for x in samples),
        'files_any_4k_window_entropy_lt_7_5': sum(x[2] < 7.5 for x in samples),
        'shared_first16_prefix_pairs': len(pairs),
        'longest_shared_prefix_bytes_within_first64': max(pairs, default=0),
        'original_executed': False,
        'idf_decoder_proven': False,
        'limitations': 'Entropy and shared prefixes do not establish compression, encryption, record layout, or decoding.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', required=True, type=Path)
    parser.add_argument('--expected-zip-sha256', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit(args.zip, args.expected_zip_sha256)
    rendered = json.dumps(report, sort_keys=True, indent=2) + '\n'
    if args.output:
        if args.output.is_symlink() or args.output.resolve() == args.zip.resolve():
            parser.error('Output must not alias original archive')
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__':
    main()
