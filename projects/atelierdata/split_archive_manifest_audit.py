"""Verify a user-owned split ZIP inventory without extraction or execution.

Checks manifest consistency, expected entries and optional streaming SHA256.
No executable is launched and no binary payload is published.
"""
import argparse
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

HEX = re.compile(r'^[0-9a-f]{64}$', re.I)
PART = re.compile(r'^.+_part_\d{4}\.zip$')


def safe_relative(name):
    if not isinstance(name, str) or not name or '\\' in name or '\0' in name:
        raise ValueError('Invalid path')
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ValueError('Unsafe path')
    return name


def inspect_manifest(data, inventory_text=None):
    if not isinstance(data, dict) or not isinstance(data.get('files'), list):
        raise ValueError('Invalid manifest')
    files, packages = {}, defaultdict(dict)
    chunks_total = 0
    total = 0
    idf_count = 0
    for row in data['files']:
        path = safe_relative(row['path'])
        size = row['size_bytes']
        chunks = row['chunks']
        if path in files or type(size) is not int or size < 0 or not chunks:
            raise ValueError('Duplicate file or invalid size/chunks')
        size_sum = 0
        for index, chunk in enumerate(chunks):
            package = chunk['package']
            entry = safe_relative(chunk['entry'])
            expected = path if len(chunks) == 1 else f'{path}.chunk{index:04d}'
            amount = chunk['bytes']
            digest = chunk['sha256']
            if (not isinstance(package, str) or not PART.fullmatch(package)
                    or entry != expected or type(amount) is not int or amount < 0
                    or amount > 1024**3 or not isinstance(digest, str)
                    or not HEX.fullmatch(digest) or entry in packages[package]):
                raise ValueError('Malformed chunk')
            packages[package][entry] = (amount, digest.lower())
            size_sum += amount
            chunks_total += 1
        if size != size_sum:
            raise ValueError('Chunk sizes do not reconstruct file')
        files[path] = size
        total += size
        idf_count += path.lower().endswith('.idf')
    if (not files or len(files) != data.get('file_count')
            or total != data.get('total_extracted_bytes')
            or len(packages) != data.get('package_count')):
        raise ValueError('Manifest counters differ from file entries')
    if inventory_text is not None:
        expected = {}
        for line in inventory_text.splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r'\s*(\d+)\s+(.+?)\s*', line)
            if not match:
                raise ValueError('Invalid text inventory')
            name = safe_relative(match[2])
            if name in expected:
                raise ValueError('Duplicate inventory row')
            expected[name] = int(match[1])
        if files != expected:
            raise ValueError('Inventory text differs from manifest')
    summary = dict(status='MANIFEST_VALID', files=len(files),
                   packages=len(packages), chunks=chunks_total,
                   bytes=total, idf_files=idf_count, executes_original=False)
    return summary, packages


def inspect_zip(path, expected, verify_sha=False):
    if path.is_symlink() or not path.is_file():
        return 'MISSING'
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            found = {m.filename: m for m in members}
            if len(found) != len(members) or set(found) != set(expected):
                raise ValueError('ZIP member list differs from inventory')
            for name, (size, sha) in expected.items():
                member = found[name]
                if member.is_dir() or member.file_size != size:
                    raise ValueError('ZIP member size mismatch')
                if verify_sha:
                    h = hashlib.sha256()
                    count = 0
                    with archive.open(member) as stream:
                        while True:
                            block = stream.read(1024 * 1024)
                            if not block:
                                break
                            count += len(block)
                            if count > size:
                                raise ValueError('Oversize member')
                            h.update(block)
                    if count != size or h.hexdigest() != sha:
                        raise ValueError('Chunk SHA256 mismatch')
        return 'SHA256_PASS' if verify_sha else 'STRUCTURE_PASS'
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError, EOFError):
        return 'FAIL'


def self_test():
    h = hashlib.sha256(b'abc').hexdigest()
    data = dict(files=[dict(path='Sample/file.IDF', size_bytes=3,
             chunks=[dict(package='sample_part_0001.zip', entry='Sample/file.IDF',
                          bytes=3, sha256=h)])],
             file_count=1, package_count=1, total_extracted_bytes=3)
    summary, packages = inspect_manifest(data, '3 Sample/file.IDF\n')
    assert (summary['files'], summary['idf_files']) == (1, 1)
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        archive = Path(d) / 'sample_part_0001.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('Sample/file.IDF', b'abc')
        assert inspect_zip(archive, packages[archive.name], True) == 'SHA256_PASS'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('Sample/file.IDF', b'xyz')
        assert inspect_zip(archive, packages[archive.name], True) == 'FAIL'
    print('SPLIT_ARCHIVE_SELF_TEST=PASS')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path)
    p.add_argument('--inventory', type=Path)
    p.add_argument('--parts-dir', type=Path)
    p.add_argument('--sha256', action='store_true')
    p.add_argument('--output', type=Path)
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.manifest is None:
        p.error('--manifest is required')
    if args.manifest.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Manifest exceeds size limit')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    inventory = args.inventory.read_text(encoding='utf-8-sig') if args.inventory else None
    result, parts = inspect_manifest(manifest, inventory)
    if args.sha256 and not args.parts_dir:
        p.error('--sha256 requires --parts-dir')
    if args.parts_dir:
        statuses = {name: inspect_zip(args.parts_dir / name, entries, args.sha256)
                    for name, entries in sorted(parts.items())}
        result['zip_statuses'] = statuses
        if not all(value.endswith('PASS') for value in statuses.values()):
            result['status'] = 'ZIP_PARTS_INCOMPLETE'
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
    return 0 if result['status'] == 'MANIFEST_VALID' else 2


if __name__ == '__main__':
    raise SystemExit(main())
