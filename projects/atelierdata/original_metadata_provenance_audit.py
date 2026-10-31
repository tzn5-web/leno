"""Bounded read-only provenance audit of four authorized Autodata metadata members.

Only part_0004 is inspected; never opens blocked part_0016, executes code,
checks licenses, extracts files, or exposes private XML text/expiry fields.
SHA256 against the owner's manifest does not prove vendor authenticity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET
import zipfile

from original_archive_preflight import BLOCKED_PACKAGE, load_manifest

PART = 'autodata_part_0004.zip'
ROOT = 'Autodata__3.45/ADCDA2/'
FILES = {
    'product': (ROOT + 'COMMON/VERINFO.DAT', 4096),
    'distributors': (ROOT + 'COMMON/distinfo.xml', 256 * 1024),
    'countries': (ROOT + 'ENG/country.xml', 256 * 1024),
    'translations': (ROOT + 'ENG/string.xml', 512 * 1024),
}
SCHEMA = 'atelierdata-original-metadata-provenance-v1'
PRODUCT_CODE = re.compile(r'^CDA(?P<version>[0-9]+\.[0-9]+)$', re.I)


def _safe_read(z: zipfile.ZipFile, name: str, limit: int, chunk: dict) -> bytes:
    if chunk['package'] == BLOCKED_PACKAGE or chunk['package'] != PART:
        raise ValueError('Expected metadata is outside the allowed part')
    infos = [i for i in z.infolist() if i.filename == name]
    if len(infos) != 1:
        raise ValueError('Missing or duplicate metadata member')
    info = infos[0]
    if info.is_dir() or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
        raise ValueError('Unsafe metadata member')
    if info.file_size > limit or info.file_size != chunk['bytes']:
        raise ValueError('Metadata size mismatch or exceeds limit')
    digest = hashlib.sha256()
    pieces = []
    count = 0
    with z.open(info, 'r') as stream:
        while True:
            data = stream.read(min(65536, limit + 1 - count))
            if not data:
                break
            count += len(data)
            if count > limit or count > chunk['bytes']:
                raise ValueError('Metadata exceeds declared size')
            digest.update(data)
            pieces.append(data)
    if count != chunk['bytes'] or digest.hexdigest() != chunk['sha256'].lower():
        raise ValueError('Metadata SHA256 mismatch')
    return b''.join(pieces)


def _product_info(data: bytes) -> dict:
    try:
        text = data.decode('ascii')
    except UnicodeError as exc:
        raise ValueError('Invalid product metadata encoding') from exc
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if not rows or rows[0] != '[PRODUCT INFORMATION]':
        raise ValueError('Unexpected product metadata section')
    fields = {}
    for line in rows[1:]:
        if '=' not in line:
            raise ValueError('Malformed product metadata')
        key, value = line.split('=', 1)
        if not key or key in fields:
            raise ValueError('Duplicate or empty product metadata key')
        fields[key] = value.strip()
    code = fields.get('ProductCode', '')
    if not PRODUCT_CODE.fullmatch(code):
        raise ValueError('ProductCode missing or unexpected format')
    return {'product_code': code, 'internal_version': fields.get('VersionNo', ''),
            'metadata_key_count': len(fields)}


def _xml_summary(data: bytes) -> dict:
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML DTD/entities forbidden')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError('Invalid XML metadata') from exc
    counts = Counter(node.tag for node in root.iter())
    return {'root_tag': root.tag, 'element_count': sum(counts.values()),
            'distinct_tag_count': len(counts)}


def audit(manifest_path: Path, parts_dir: Path) -> dict:
    manifest, entries = load_manifest(manifest_path)
    directory = Path(parts_dir).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('Parts path must be a directory')
    archive_path = directory / PART
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError('Allowed metadata package unavailable')
    source = manifest.get('archive', '')
    declared = re.search(r'Autodata__([0-9]+\.[0-9]+)', source)
    if not declared:
        raise ValueError('Archive label does not declare a version')
    chunks = {}
    for label, (name, _) in FILES.items():
        meta = entries.get((PART, name))
        if not meta or meta['file'] != name:
            raise ValueError('Metadata missing or split across packages')
        chunks[label] = {'package': PART, 'bytes': meta['size'], 'sha256': meta['sha256']}
    with zipfile.ZipFile(archive_path, 'r') as z:
        parsed = {}
        for label, (name, limit) in FILES.items():
            raw = _safe_read(z, name, limit, chunks[label])
            parsed[label] = _product_info(raw) if label == 'product' else _xml_summary(raw)
    product = parsed.pop('product')
    code_version = PRODUCT_CODE.fullmatch(product['product_code']).group('version')
    label_version = declared.group(1)
    return {
        'schema': SCHEMA,
        'scope': 'four_sha256_verified_members_of_authorized_part_0004',
        'verified_member_count': len(FILES),
        'archive_label_version': label_version,
        'product_code': product['product_code'],
        'internal_version': product['internal_version'],
        'metadata_key_count': product['metadata_key_count'],
        'label_product_code_match': label_version == code_version,
        'version_observation': ('MATCH' if label_version == code_version else
                                'LABEL_PRODUCT_CODE_DIFFER_NOT_PROOF_OF_DEFECT'),
        'xml_metadata': parsed,
        'original_executed': False,
        'blocked_package_accessed': False,
        'license_validated': False,
        'installer_validated': False,
        'publisher_authenticity_validated': False,
        'idf_decoded': False,
        'windows_runtime_tested': False,
        'conclusion': 'Metadata is intact against owner manifest; version difference alone cannot establish a broken installation.',
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--parts-dir', type=Path, required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = audit(args.manifest, args.parts_dir)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload, encoding='utf-8')
    print(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
