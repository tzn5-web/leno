"""Inspect SHA256-verified split data files, without exporting their content.

Only temporary, automatically unlinked scratch storage is used; no original
executables are run, and no proprietary data is written to the repository.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import tempfile
import zipfile
from pathlib import Path

from split_archive_manifest_audit import inspect_manifest

WINDOW = 65536


def entropy(data):
    if not data:
        return 0.0
    freq = collections.Counter(data)
    return round(-sum((n / len(data)) * math.log2(n / len(data)) for n in freq.values()), 4)


def audit(manifest, directory):
    inspect_manifest(manifest)
    directory = Path(directory).resolve(strict=True)
    archives = {}
    samples = []
    try:
        for row in manifest['files']:
            if not row['path'].lower().endswith('.idf'):
                continue
            with tempfile.TemporaryFile() as scratch:
                total = 0
                for chunk in row['chunks']:
                    package = chunk['package']
                    if package not in archives:
                        source = directory / package
                        if source.is_symlink():
                            raise ValueError('Refuse symlink package')
                        archives[package] = zipfile.ZipFile(source)
                    info = archives[package].getinfo(chunk['entry'])
                    if info.file_size != chunk['bytes'] or info.file_size > 1024**3:
                        raise ValueError('Chunk size mismatch')
                    checksum = hashlib.sha256()
                    count = 0
                    with archives[package].open(info) as stream:
                        while True:
                            block = stream.read(1024 * 1024)
                            if not block:
                                break
                            count += len(block)
                            if count > chunk['bytes']:
                                raise ValueError('Oversize chunk')
                            checksum.update(block)
                            scratch.write(block)
                    if count != chunk['bytes'] or checksum.hexdigest() != chunk['sha256'].lower():
                        raise ValueError('Chunk SHA256 mismatch')
                    total += count
                if total != row['size_bytes']:
                    raise ValueError('Reconstructed size mismatch')
                size = min(WINDOW, total)
                positions = (0, max(0, (total - size) // 2), max(0, total - size))
                sections = []
                for position in positions:
                    scratch.seek(position)
                    sections.append(scratch.read(size))
                entropies = [entropy(value) for value in sections]
                samples.append({
                    'path': row['path'], 'bytes': total,
                    'window_entropies': entropies,
                    'all_windows_entropy_ge_7_95': all(x >= 7.95 for x in entropies),
                    'familiar_compressed_header': sections[0].startswith(
                        (b'PK\x03\x04', b'\x1f\x8b', b'\x78\x9c', b'\x78\xda')),
                    'sha256_all_chunks_pass': True
                })
    finally:
        for archive in archives.values():
            archive.close()
    aggregate = {
        'schema': 'atelierdata-idf-complete-static-summary-v1',
        'idf_files': len(samples),
        'idf_total_bytes': sum(row['bytes'] for row in samples),
        'files_all_chunks_sha256_verified': len(samples),
        'high_entropy_in_all_three_windows': sum(row['all_windows_entropy_ge_7_95'] for row in samples),
        'familiar_compression_headers': sum(row['familiar_compressed_header'] for row in samples),
        'target_executed': False,
        'decoder_proven': False,
        'note': 'High entropy is not evidence of a particular encryption or compression scheme.'
    }
    return aggregate, samples


def self_test():
    from tempfile import TemporaryDirectory
    b1, b2 = b'abc', b'xyz'
    def chunk(part, entry, data):
        return dict(package=part, entry=entry, bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest())
    manifest = {
        'files': [dict(path='Sample/X.IDF', size_bytes=6,
                       chunks=[chunk('sample_part_0001.zip', 'Sample/X.IDF.chunk0000', b1),
                               chunk('sample_part_0002.zip', 'Sample/X.IDF.chunk0001', b2)])],
        'file_count': 1, 'package_count': 2, 'total_extracted_bytes': 6
    }
    with TemporaryDirectory() as tmp:
        for number, block in ((1, b1), (2, b2)):
            with zipfile.ZipFile(Path(tmp) / f'sample_part_{number:04d}.zip', 'w') as archive:
                archive.writestr(f'Sample/X.IDF.chunk{number-1:04d}', block)
        result, records = audit(manifest, tmp)
        assert result['idf_files'] == 1 and result['idf_total_bytes'] == 6
        assert len(records) == 1 and records[0]['sha256_all_chunks_pass']
    print('COMPLETE_IDF_STATIC_SELF_TEST=PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--parts-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--private-details', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.manifest is None or args.parts_dir is None:
        parser.error('--manifest and --parts-dir are required')
    if args.manifest.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Oversize manifest')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    result, rows = audit(manifest, args.parts_dir)
    public = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(public, encoding='utf-8')
    if args.private_details:
        args.private_details.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n',
                                        encoding='utf-8')
    print(public)


if __name__ == '__main__':
    main()
