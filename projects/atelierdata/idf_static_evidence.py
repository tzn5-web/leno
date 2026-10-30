"""Metadata-only static IDF evidence. No execution, decoding or license bypass."""
from __future__ import annotations
import argparse, collections, hashlib, json, math, tempfile, zipfile
from pathlib import Path

MAX_ENTRY = 64 * 1024 * 1024
TERMS = ('MODELS.IDF', 'CONST.IDF', 'CSS.IDF', 'DTC.IDF', '.IDF',
         'inflate 1.2.3', 'TFRMAUTODATABASE')


def entropy(blob):
    if not blob:
        return 0.0
    freq = collections.Counter(blob)
    return round(-sum((n / len(blob)) * math.log2(n / len(blob)) for n in freq.values()), 4)


def windows(blob):
    size = min(len(blob), 65536)
    if not size:
        return {'first': 0.0, 'middle': 0.0, 'last': 0.0}
    middle = max(0, (len(blob) - size) // 2)
    return {'first': entropy(blob[:size]), 'middle': entropy(blob[middle:middle + size]),
            'last': entropy(blob[-size:])}


def inventory_index(path):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    result = {}
    for file in manifest['files']:
        for chunk in file.get('chunks', []):
            result[(chunk['package'], chunk['entry'])] = {
                'sha256': chunk['sha256'], 'bytes': chunk['bytes']}
    return result


def scan_executable(path, expected_sha=None):
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if expected_sha and sha.lower() != expected_sha.lower():
        raise ValueError('Original EXE SHA256 mismatch')
    patterns = {}
    for term in TERMS:
        patterns[term] = {}
        for encoding in ('ascii', 'utf-16le'):
            needle = term.encode(encoding)
            locations, start = [], 0
            while True:
                found = data.find(needle, start)
                if found < 0:
                    break
                if len(locations) < 12:
                    locations.append(found)
                start = found + 1
            patterns[term][encoding] = {
                'first_offsets': locations,
                'count_at_least': min(len(locations), 12),
                'truncated': len(locations) >= 12}
    return {'bytes': len(data), 'sha256': sha, 'expected_sha_verified': bool(expected_sha),
            'executed': False, 'literal_pattern_observations': patterns}


def scan_archives(archives, index, names):
    rows, skipped = [], []
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith('.idf'):
                    continue
                if names and Path(info.filename).name.upper() not in names:
                    continue
                if info.file_size > MAX_ENTRY:
                    skipped.append({'archive': archive.name, 'entry': info.filename,
                                    'reason': 'entry exceeds 64 MiB limit'})
                    continue
                expected = index.get((archive.name, info.filename))
                if not expected:
                    raise ValueError('Unverified archive entry: ' + archive.name + ':' + info.filename)
                if expected['bytes'] != info.file_size:
                    raise ValueError('Manifest size mismatch: ' + info.filename)
                with z.open(info) as inp:
                    blob = inp.read(MAX_ENTRY + 1)
                if len(blob) != info.file_size:
                    raise ValueError('Archive read length mismatch: ' + info.filename)
                digest = hashlib.sha256(blob).hexdigest()
                if digest != expected['sha256']:
                    raise ValueError('Manifest SHA256 mismatch: ' + info.filename)
                sample = blob[:min(len(blob), 65536)]
                rows.append({'archive': archive.name, 'entry': info.filename,
                             'bytes': len(blob), 'sha256': digest, 'sha256_verified': True,
                             'entropy_bits_per_byte': windows(blob),
                             'first_window_printable_fraction': round(
                                 sum(32 <= v <= 126 for v in sample) / max(1, len(sample)), 4),
                             'first_window_null_fraction': round(
                                 sample.count(0) / max(1, len(sample)), 4),
                             'decoded': False})
    return {'samples': rows, 'skipped': skipped, 'verified_samples': len(rows)}


def self_test():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        entry = 'Sample/COMMON/FAKE.IDF'
        data = bytes(range(256)) * 3
        with zipfile.ZipFile(root / 'test.zip', 'w') as z:
            z.writestr(entry, data)
        index = {('test.zip', entry): {
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}}
        result = scan_archives([root / 'test.zip'], index, {'FAKE.IDF'})
        assert result['verified_samples'] == 1
        assert result['samples'][0]['entropy_bits_per_byte']['first'] == 8.0
        assert not result['samples'][0]['decoded']
        index[('test.zip', entry)]['sha256'] = '0' * 64
        try:
            scan_archives([root / 'test.zip'], index, {'FAKE.IDF'})
        except ValueError:
            pass
        else:
            raise AssertionError('SHA256 mismatch was not rejected')
    print('IDF_STATIC_EVIDENCE_SELF_TEST=PASS')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip', nargs='+', type=Path)
    p.add_argument('--inventory', type=Path)
    p.add_argument('--names', nargs='*', default=[])
    p.add_argument('--exe', type=Path)
    p.add_argument('--expected-exe-sha256')
    p.add_argument('--output', type=Path)
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if a.self_test:
        return self_test()
    if not a.zip or not a.inventory or not a.output:
        p.error('--zip, --inventory and --output are required')
    report = {'analysis': 'metadata-only static analysis', 'idf_decoder_proven': False,
              'target_executed': False,
              'archives': scan_archives(a.zip, inventory_index(a.inventory),
                                        {n.upper() for n in a.names})}
    if a.exe:
        report['executable'] = scan_executable(a.exe, a.expected_exe_sha256)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('IDF_STATIC_EVIDENCE=PASS verified_samples=' +
          str(report['archives']['verified_samples']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
