"""Read-only IDF prefix-family evidence from owner-authorized split ZIP files.

Verifies SHA256 of each first chunk; never exports bytes, runs executables,
or claims IDF decoding. Public output contains aggregate counts only.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import itertools
import json
import zipfile
from pathlib import Path
from split_archive_manifest_audit import inspect_manifest

WINDOW = 65536
MAX_CHUNK = 1024 ** 3


def first_chunk_sample(root, chunk, archives):
    name = chunk['package']
    if name not in archives:
        path = root / name
        if path.is_symlink():
            raise ValueError('Symlink archive refused')
        archives[name] = zipfile.ZipFile(path)
    archive = archives[name]
    member = archive.getinfo(chunk['entry'])
    if member.is_dir() or member.file_size != chunk['bytes'] or member.file_size > MAX_CHUNK:
        raise ValueError('Chunk size mismatch')
    digest = hashlib.sha256()
    sample = bytearray()
    total = 0
    with archive.open(member) as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > member.file_size:
                raise ValueError('Chunk exceeded declared size')
            digest.update(block)
            if len(sample) < WINDOW:
                sample.extend(block[:WINDOW - len(sample)])
    if total != member.file_size or digest.hexdigest() != chunk['sha256'].lower():
        raise ValueError('First chunk SHA256 mismatch')
    return bytes(sample)


def common_prefix_length(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right))


def audit(manifest, directory):
    inspect_manifest(manifest)
    root = Path(directory).resolve(strict=True)
    archives = {}
    samples = {}
    try:
        for item in manifest['files']:
            if item['path'].lower().endswith('.idf'):
                samples[item['path']] = first_chunk_sample(root, item['chunks'][0], archives)
    finally:
        for archive in archives.values():
            archive.close()
    groups = collections.defaultdict(list)
    for name, sample in samples.items():
        groups[sample[:16]].append(name)
    repeated = []
    for members in groups.values():
        if len(members) < 2:
            continue
        for left, right in itertools.combinations(members, 2):
            repeated.append({'left': left, 'right': right,
                             'shared_prefix_bytes': common_prefix_length(samples[left], samples[right]),
                             'window_limit_bytes': min(len(samples[left]),len(samples[right]))})
    public = {
        'schema': 'atelierdata-idf-prefix-family-v1',
        'idf_files': len(samples),
        'first_chunks_sha256_verified': len(samples),
        'distinct_first16_prefixes': len(groups),
        'repeated_first16_pairs': len(repeated),
        'max_shared_prefix_bytes': max((r['shared_prefix_bytes'] for r in repeated),default=0),
        'target_executed': False,
        'decoder_proven': False,
        'note': 'Shared prefixes imply related binary structure, not an identified decoder or encryption scheme.'
    }
    return public, repeated


def self_test():
    import tempfile
    a, b, c = b'A'*20+b'1'*32, b'A'*20+b'2'*32, b'B'*52
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        records = []
        for number, blob in enumerate((a,b,c),1):
            name = f'sample_part_{number:04d}.zip'
            entry = f'TEST/TEST{number}.IDF'
            with zipfile.ZipFile(root / name, 'w') as archive:
                archive.writestr(entry, blob)
            records.append({'path':entry,'size_bytes':len(blob),
                            'chunks':[{'package':name,'entry':entry,'bytes':len(blob),
                                       'sha256':hashlib.sha256(blob).hexdigest()}]})
        manifest = {'files':records,'file_count':3,'package_count':3,
                    'total_extracted_bytes':sum(len(x) for x in (a,b,c))}
        summary, pairs = audit(manifest,root)
        assert summary['first_chunks_sha256_verified']==3
        assert summary['distinct_first16_prefixes']==2
        assert summary['repeated_first16_pairs']==1
        assert summary['max_shared_prefix_bytes']==20
        assert pairs[0]['shared_prefix_bytes']==20
        manifest['files'][0]['chunks'][0]['sha256']='0'*64
        try:
            audit(manifest,root)
        except ValueError:
            pass
        else:
            raise AssertionError('Hash mismatch accepted')
    print('IDF_PREFIX_FAMILY_SELF_TEST=PASS')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--parts-dir',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--private-details',type=Path)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.manifest or not args.parts_dir:
        parser.error('--manifest and --parts-dir required')
    if args.manifest.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Oversize manifest')
    manifest=json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    summary, pairs=audit(manifest,args.parts_dir)
    public=json.dumps(summary,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.write_text(public,encoding='utf-8')
    if args.private_details:
        args.private_details.write_text(json.dumps(pairs,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(public)


if __name__=='__main__':
    main()
