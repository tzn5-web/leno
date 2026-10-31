"""Private, read-only IDF prefix comparison with per-chunk SHA256 verification.

No decoder, decryption, execution, extraction, or proprietary bytes in public output.
Only owner-authorized ZIPs are read; part_0016 is categorically excluded.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import zipfile
from pathlib import Path

from original_archive_preflight import BLOCKED_PACKAGE, load_manifest

SCHEMA = 'atelierdata-idf-prefix-provenance-v1'
SAMPLE = 4096
CHUNK = 1024 * 1024
PREFIX_THRESHOLDS = (4, 8, 16, 20, 32, 64)
# Only recognize well-known signatures; absence does not identify encryption.
MAGICS = (b'SQLite format 3\0', b'PK\x03\x04', b'\x1f\x8b', b'\x89PNG\r\n\x1a\n',
          b'%PDF-', b'7z\xbc\xaf\x27\x1c', b'Rar!\x1a\x07')


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = collections.Counter(data)
    return -sum((count / len(data)) * math.log2(count / len(data)) for count in freq.values())


def _prefix_length(left: bytes, right: bytes) -> int:
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right))


def audit(manifest_path: Path, parts_dir: Path, selected_packages: list[str]) -> dict:
    manifest, _ = load_manifest(manifest_path)
    packages = set(selected_packages)
    if not packages or len(packages) != len(selected_packages):
        raise ValueError('Specify unique authorized package names')
    known = {chunk['package'] for row in manifest['files'] for chunk in row['chunks']}
    if BLOCKED_PACKAGE in packages or not packages <= known:
        raise ValueError('Blocked or unknown package')
    if any('/' in p or '\\' in p for p in packages):
        raise ValueError('Package name must be a basename')
    root = Path(parts_dir)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Parts directory is invalid')
    idfs = [row for row in manifest['files'] if row['path'].lower().endswith('.idf')]
    selected = []
    multi = 0
    for row in idfs:
        chunks = row['chunks']
        if len(chunks) > 1:
            if any(chunk['package'] in packages for chunk in chunks):
                multi += 1
            continue
        if chunks[0]['package'] in packages:
            selected.append(chunks[0])
    if not selected:
        raise ValueError('No complete single-chunk IDF in selected packages')
    samples = []
    verified_bytes = 0
    for package in sorted(packages):
        targets = [c for c in selected if c['package'] == package]
        if not targets:
            continue
        path = root / package
        if path.is_symlink() or not path.is_file():
            raise ValueError('Selected authorized package is missing or a symlink')
        with zipfile.ZipFile(path) as archive:
            names = collections.Counter(info.filename for info in archive.infolist())
            for chunk in targets:
                entry = chunk['entry']
                if names[entry] != 1:
                    raise ValueError('Missing or duplicated IDF ZIP entry')
                info = archive.getinfo(entry)
                if (info.is_dir() or info.flag_bits & 1 or info.file_size != chunk['bytes']
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('Unsafe or mismatched IDF entry')
                digest = hashlib.sha256()
                size = 0
                sample = bytearray()
                with archive.open(info) as stream:
                    while True:
                        block = stream.read(CHUNK)
                        if not block:
                            break
                        size += len(block)
                        if size > chunk['bytes']:
                            raise ValueError('IDF exceeds manifest size')
                        digest.update(block)
                        if len(sample) < SAMPLE:
                            sample.extend(block[:SAMPLE - len(sample)])
                if size != chunk['bytes'] or digest.hexdigest() != chunk['sha256'].lower():
                    raise ValueError('IDF SHA256 differs from owner manifest')
                samples.append(bytes(sample))
                verified_bytes += size
    if not samples:
        raise ValueError('No IDF entries inspected')
    pairs = {str(n): 0 for n in PREFIX_THRESHOLDS}
    longest = 0
    for i, first in enumerate(samples):
        for second in samples[i + 1:]:
            shared = _prefix_length(first, second)
            longest = max(longest, shared)
            for threshold in PREFIX_THRESHOLDS:
                if shared >= threshold:
                    pairs[str(threshold)] += 1
    magic_hits = sum(any(sample.startswith(magic) for magic in MAGICS) for sample in samples)
    entropies = [_entropy(s) for s in samples if len(s) >= 256]
    return {
        'schema': SCHEMA,
        'selected_authorized_packages': len(packages),
        'single_chunk_idf_sha256_verified': len(samples),
        'verified_idf_bytes': verified_bytes,
        'multipart_idf_not_analyzed': multi,
        'compared_pairs': len(samples) * (len(samples) - 1) // 2,
        'shared_prefix_pairs_at_least_bytes': pairs,
        'longest_shared_sample_prefix_bytes': longest,
        'known_container_magic_hits': magic_hits,
        'entropy_sample_bytes': SAMPLE,
        'mean_sample_entropy_bits_per_byte': (round(sum(entropies) / len(entropies), 4)
                                               if entropies else None),
        'sha256_compared_to': 'owner_provided_manifest_not_vendor_signature',
        'raw_headers_in_public_report': False,
        'original_executed': False,
        'idf_decoded': False,
        'license_or_vendor_authenticity_verified': False,
        'interpretation': 'Matching prefixes are format clues only; neither high entropy '
                          'nor repeated headers establish encryption, a decoder, or a license.'
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--parts-dir', required=True, type=Path)
    parser.add_argument('--package', action='append', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.manifest, args.parts_dir, args.package)
        encoded = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
        if args.output:
            protected = {args.manifest.resolve()}
            protected.update((args.parts_dir / p).resolve() for p in args.package)
            if args.output.resolve() in protected:
                raise ValueError('Output may not overwrite an input')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding='utf-8')
        print(encoded)
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
            RuntimeError, EOFError) as exc:
        # No original paths, filenames, hashes or ZIP entry bytes in errors.
        print(json.dumps({'schema': SCHEMA, 'status': 'FAIL',
                          'error_type': type(exc).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
