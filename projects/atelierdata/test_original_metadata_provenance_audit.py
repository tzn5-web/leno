"""Synthetic regression tests; no original private archive in CI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from original_metadata_provenance_audit import FILES, PART, _product_info, _xml_summary, audit


class MetadataProvenanceTests(unittest.TestCase):
    def fixture(self, directory, version='3.45', code='CDA3.44', tamper=None, missing=None):
        payloads = {
            'product': f'[PRODUCT INFORMATION]\r\nProductCode={code}\r\nVersionNo=9.200\r\nExpiryDate=PRIVATE\r\n'.encode(),
            'distributors': b'<Distributors><Distributor><Name>PRIVATE</Name></Distributor></Distributors>',
            'countries': b'<Countries><country><label5>PRIVATE</label5></country></Countries>',
            'translations': b'<AllText><Text>PRIVATE</Text><Text>PRIVATE</Text></AllText>',
        }
        manifest = {'archive': f'Autodata__{version}.rar', 'files': []}
        with zipfile.ZipFile(directory / PART, 'w') as z:
            for label, (name, _) in FILES.items():
                raw = payloads[label]
                manifest['files'].append({'path': name, 'size_bytes': len(raw), 'chunks': [
                    {'package': PART, 'entry': name, 'bytes': len(raw),
                     'sha256': hashlib.sha256(raw).hexdigest()}]})
                if label != missing:
                    z.writestr(name, (raw + b'bad') if label == tamper else raw)
        path = directory / 'manifest.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        return path

    def test_version_difference_is_observation_not_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p)
            r = audit(m, p)
            self.assertEqual(r['verified_member_count'], 4)
            self.assertFalse(r['label_product_code_match'])
            self.assertEqual(r['version_observation'], 'LABEL_PRODUCT_CODE_DIFFER_NOT_PROOF_OF_DEFECT')
            self.assertEqual(r['xml_metadata']['translations']['element_count'], 3)
            self.assertNotIn('PRIVATE', json.dumps(r))
            self.assertFalse(r['installer_validated'])

    def test_matching_versions(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p, code='CDA3.45')
            self.assertTrue(audit(m, p)['label_product_code_match'])

    def test_sha_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p, tamper='countries')
            with self.assertRaisesRegex(ValueError, 'size mismatch|SHA256 mismatch'):
                audit(m, p)

    def test_missing_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p, missing='product')
            with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                audit(m, p)

    def test_duplicate_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p)
            with zipfile.ZipFile(p / PART, 'a') as z:
                z.writestr(FILES['product'][0], b'forged')
            with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                audit(m, p)

    def test_product_metadata_duplicate_key(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            _product_info(b'[PRODUCT INFORMATION]\nProductCode=CDA3.44\nProductCode=CDA3.45\n')

    def test_product_metadata_bad_header(self):
        with self.assertRaisesRegex(ValueError, 'section'):
            _product_info(b'ProductCode=CDA3.45\n')

    def test_xml_entity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DTD/entities'):
            _xml_summary(b'<!DOCTYPE foo [<!ENTITY x "secret">]><foo>&x;</foo>')

    def test_xml_malformed_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid XML'):
            _xml_summary(b'<foo>')

    def test_manifest_cannot_retarget_to_blocked_package(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p)
            manifest = json.loads(m.read_text())
            manifest['files'][0]['chunks'][0]['package'] = 'autodata_part_0016.zip'
            m.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'missing or split'):
                audit(m, p)

    def test_symlink_part_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); m = self.fixture(p)
            real = p / 'real.zip'
            (p / PART).rename(real)
            try:
                (p / PART).symlink_to(real)
            except (OSError, NotImplementedError):
                self.skipTest('Symlink creation not available')
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                audit(m, p)


if __name__ == '__main__':
    unittest.main()
