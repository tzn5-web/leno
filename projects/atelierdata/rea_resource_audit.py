"""Validate REA PE-resource evidence against an authorized local PE, without executing it.

Public output contains only aggregate statistics. Never decode or export protected payloads.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
import statistics
import tempfile
from pathlib import Path

MAX_PE = 64 * 1024 * 1024
MAX_REPORT = 16 * 1024 * 1024
DIB_HEADERS = {12, 40, 52, 56, 108, 124}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def entropy(blob):
    if not blob:
        return 0.0
    counts = collections.Counter(blob)
    return -sum((n / len(blob)) * math.log2(n / len(blob)) for n in counts.values())


def analyze(binary, rea, expected_sha):
    if len(binary) < 64 or len(binary) > MAX_PE or binary[:2] != b'MZ':
        raise ValueError("Invalid PE or size")
    if len(expected_sha) != 64 or any(c not in '0123456789abcdefABCDEF' for c in expected_sha):
        raise ValueError("Invalid expected SHA256")
    digest = sha(binary)
    if digest != expected_sha.lower():
        raise ValueError("Original PE SHA256 mismatch")
    normalized = rea.get('normalized_result', {})
    if (rea.get('provider', {}).get('id') != 'rea-pe-resources' or
        rea.get('subject', {}).get('digest', {}).get('sha256') != digest or
        normalized.get('artifact', {}).get('sha256') != digest or
        normalized.get('artifact', {}).get('bytes') != len(binary)):
        raise ValueError("REA report belongs to another binary")
    rows = normalized.get('resources')
    if not isinstance(rows, list) or len(rows) > 16384:
        raise ValueError("Missing or excessive resources")
    coverage = normalized.get('coverage', {})
    if coverage.get('status') != 'complete' or coverage.get('resources') != len(rows):
        raise ValueError("Incomplete REA resource coverage")
    groups = collections.defaultdict(lambda: dict(
        count=0, payload_bytes=0, samples_ge_1024=0, entropy_values=[],
        entropy_ge_7_9_count_ge_4096=0, binary_dfm_headers=0,
        text_dfm_headers=0, dib_headers=0))
    private = []
    for index, row in enumerate(rows):
        loc = row.get('payload', {}).get('location', {})
        start, size = loc.get('offset'), loc.get('bytes')
        if (type(start) is not int or type(size) is not int or start < 0 or size < 0
            or start > len(binary) or size > len(binary) - start):
            raise ValueError(f"Resource {index}: invalid bounds")
        payload = binary[start:start + size]
        digest_payload = sha(payload)
        if digest_payload != row['payload'].get('sha256'):
            raise ValueError(f"Resource {index}: SHA256 mismatch")
        type_obj = row.get('type', {})
        resource_type = str(type_obj.get('id', type_obj.get('name', 'unknown')))
        name_obj = row.get('name', {})
        name = str(name_obj.get('name', name_obj.get('id', 'unknown')))
        sample = payload[:65536]
        bits = round(entropy(sample), 4)
        group = groups[resource_type]
        group['count'] += 1
        group['payload_bytes'] += size
        if size >= 1024:
            group['samples_ge_1024'] += 1
            group['entropy_values'].append(bits)
        if size >= 4096 and bits >= 7.9:
            group['entropy_ge_7_9_count_ge_4096'] += 1
        binary_dfm = payload.startswith(b'TPF0')
        text_dfm = payload.startswith((b'object ', b'inherited '))
        dib = len(payload) >= 4 and int.from_bytes(payload[:4], 'little') in DIB_HEADERS
        if resource_type == '10':
            group['binary_dfm_headers'] += int(binary_dfm)
            group['text_dfm_headers'] += int(text_dfm)
        if resource_type == '2':
            group['dib_headers'] += int(dib)
        private.append(dict(index=index, type=resource_type, name=name,
                            offset=start, bytes=size, sha256=digest_payload,
                            first_window_entropy=bits, binary_dfm=binary_dfm,
                            text_dfm=text_dfm, dib_header=dib))
    aggregates = {}
    for key in sorted(groups):
        group = groups[key]
        values = group.pop('entropy_values')
        group['median_first_window_entropy_ge_1024'] = (
            round(statistics.median(values), 4) if values else None)
        aggregates[key] = group
    public = dict(schema='atelierdata-rea-resource-aggregate-v1',
                  binary_sha256=digest, binary_bytes=len(binary),
                  rea_coverage=coverage['status'], resource_count=len(rows),
                  resource_types=aggregates, target_executed=False,
                  idf_decoder_proven=False, payloads_decoded=False,
                  interpretation="Entropy and absent familiar DFM/DIB headers do not prove encryption, compression or IDF format.",
                  privacy="Aggregates only: no original payloads, names or offsets.")
    return public, dict(schema='atelierdata-rea-resource-private-v1',
                        binary_sha256=digest, resources=private)


def read_limited(path, limit):
    with Path(path).open('rb') as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds size limit")
    return data


def run(pe, rea_json, expected_sha, public_output, private_output=None):
    binary = read_limited(pe, MAX_PE)
    rea = json.loads(read_limited(rea_json, MAX_REPORT).decode('utf-8'))
    public, private = analyze(binary, rea, expected_sha)
    if private_output and Path(public_output).resolve() == Path(private_output).resolve():
        raise ValueError("Public and private paths must differ")
    for destination, payload in ((public_output, public), (private_output, private)):
        if destination is None:
            continue
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return public


def self_test():
    binary = b'MZ' + bytes(62) + b'TPF0' + bytes(60) + b'\x28\x00\x00\x00' + bytes(100)
    digest = sha(binary)
    rows = []
    for start, size, kind in ((64, 64, 10), (128, 104, 2)):
        rows.append(dict(type={'id': kind}, name={'name': 'PRIVATE_SYNTHETIC'},
                         payload={'location': {'offset': start, 'bytes': size},
                                  'sha256': sha(binary[start:start + size])}))
    rea = dict(provider={'id': 'rea-pe-resources'},
               subject={'digest': {'sha256': digest}},
               normalized_result=dict(artifact={'sha256': digest, 'bytes': len(binary)},
                                      coverage={'status': 'complete', 'resources': 2},
                                      resources=rows))
    public, _ = analyze(binary, rea, digest)
    assert public['resource_types']['10']['binary_dfm_headers'] == 1
    assert public['resource_types']['2']['dib_headers'] == 1
    for kind in ('subject', 'payload', 'bounds', 'coverage'):
        altered = json.loads(json.dumps(rea))
        if kind == 'subject':
            altered['subject']['digest']['sha256'] = '0' * 64
        elif kind == 'payload':
            altered['normalized_result']['resources'][0]['payload']['sha256'] = '0' * 64
        elif kind == 'bounds':
            altered['normalized_result']['resources'][0]['payload']['location']['offset'] = len(binary) + 1
        else:
            altered['normalized_result']['coverage']['status'] = 'partial'
        try:
            analyze(binary, altered, digest)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid {kind} accepted")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root/'sample.exe').write_bytes(binary)
        (root/'rea.json').write_text(json.dumps(rea), encoding='utf-8')
        run(root/'sample.exe', root/'rea.json', digest, root/'public.json', root/'private.json')
        assert 'PRIVATE_SYNTHETIC' not in (root/'public.json').read_text()
        assert 'PRIVATE_SYNTHETIC' in (root/'private.json').read_text()
    print('REA_RESOURCE_AUDIT_SELF_TEST=PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe', type=Path)
    parser.add_argument('--rea-json', type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--public-output', type=Path)
    parser.add_argument('--private-output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        if not all((args.pe, args.rea_json, args.expected_sha256, args.public_output)):
            parser.error('Required --pe, --rea-json, --expected-sha256, --public-output')
        result = run(args.pe, args.rea_json, args.expected_sha256,
                     args.public_output, args.private_output)
        print('REA_RESOURCE_AUDIT=PASS resource_count=' + str(result['resource_count']))
