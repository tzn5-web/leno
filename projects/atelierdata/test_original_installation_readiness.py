"""Synthetic-only tests: no proprietary payloads or license material."""
import json
import tempfile
import unittest
from pathlib import Path
from original_installation_readiness import analyze_manifest, build_report, ENTRY, ROOT, APP


def file_row(name, package, digest='a'*64, size=10):
    return {'path': name, 'size_bytes': size,
            'chunks': [{'package': package, 'entry': name, 'bytes': size, 'sha256': digest}]}


def example():
    return {'package_count': 3, 'files': [
        file_row(ENTRY, 'autodata_part_0001.zip', 'a'*64),
        file_row(APP+'COMMON/MODELS.IDF', 'autodata_part_0001.zip', 'b'*64),
        file_row(APP+'SentinelKeyW.DLL', 'autodata_part_0003.zip', 'c'*64),
        file_row(ROOT+'Install-x32.cmd', 'autodata_part_0003.zip', 'd'*64),
        file_row(ROOT+'Keygen/license.exe', 'autodata_part_0003.zip', 'e'*64),
        file_row(ROOT+'Keygen/copy.exe', 'autodata_part_0003.zip', 'e'*64),
        file_row(APP+'RelLic.dll', 'autodata_part_0002.zip', 'f'*64),
    ]}


class InstallationReadinessTests(unittest.TestCase):
    def test_missing_installer_and_sentinel_are_not_assumed_fixable(self):
        report = analyze_manifest(example(), {'autodata_part_0001.zip','autodata_part_0002.zip'})
        self.assertEqual(report['idf_wholly_in_present_packages'], 1)
        self.assertEqual(report['root_runtime_dlls']['RelLic.dll'], 'packages_present_not_hash_verified')
        self.assertEqual(report['root_runtime_dlls']['SentinelKeyW.DLL'], 'package_unavailable')
        self.assertEqual(report['named_installer_entries_accessible'], 0)
        self.assertEqual(report['conclusion'], 'NOT_READY_FOR_ORIGINAL_WINDOWS_EXECUTION')

    def test_duplicate_detection_uses_hash_and_size_not_size_alone(self):
        report = analyze_manifest(example(), set())
        groups = report['manifest_declared_equal_sha256_groups_unverified_when_package_absent']
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['names'], ['copy.exe','license.exe'])
        self.assertTrue(groups[0]['all_in_unavailable_packages'])

    def test_present_packages_are_not_claimed_hash_verified(self):
        report = analyze_manifest(example(), {'autodata_part_0001.zip'})
        self.assertEqual(report['main_executable']['status'], 'packages_present_not_hash_verified')
        self.assertFalse(report['authenticity_verified'])
        self.assertFalse(report['original_executed'])

    def test_package_count_and_unknown_packages_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Package count mismatch'):
            analyze_manifest({**example(), 'package_count': 4}, set())
        with self.assertRaisesRegex(ValueError, 'Unknown package'):
            analyze_manifest(example(), {'autodata_part_9999.zip'})

    def test_all_packages_present_still_does_not_prove_license(self):
        report = analyze_manifest(example(), {'autodata_part_0001.zip','autodata_part_0002.zip','autodata_part_0003.zip'})
        self.assertEqual(report['idf_requiring_unavailable_packages'], 0)
        self.assertEqual(report['named_installer_entries_accessible'], 1)
        self.assertFalse(report['license_checked'])
        self.assertEqual(report['conclusion'], 'NOT_READY_FOR_ORIGINAL_WINDOWS_EXECUTION')

    def test_manifest_path_traversal_rejected_by_loader(self):
        data = example()
        data['files'][0]['path'] = ROOT + '../ADBCD.exe'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'manifest.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                build_report(path)

    def test_manifest_only_report_does_not_require_private_zip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'manifest.json'
            path.write_text(json.dumps(example()), encoding='utf-8')
            result = build_report(path)
            self.assertEqual(result['available_package_count'], 0)
            self.assertNotIn('static_runtime_evidence', result)
            self.assertEqual(result['file_count'], 7)


if __name__ == '__main__':
    unittest.main()
