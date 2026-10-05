import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('vanced_audit', ROOT / 'Scripts' / 'audit.py')
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class AuditSelfTests(unittest.TestCase):
    def test_dependency_refs_are_exact_commits(self):
        lock = MODULE.load_json(MODULE.LOCK)
        refs = [lock['theos']['ref']]
        refs += [x['ref'] for x in lock.get('headers', [])]
        refs += [x['ref'] for x in lock.get('modules', [])]
        self.assertTrue(refs)
        self.assertTrue(all(MODULE.is_sha40(x) for x in refs))

    def test_feature_sets_match(self):
        matrix = MODULE.load_json(MODULE.MATRIX)
        status = MODULE.load_json(MODULE.STATUS)
        matrix_ids = {x['id'] for x in matrix['required']}
        status_ids = set(status['features'])
        self.assertEqual(matrix_ids, MODULE.REQUIRED_FEATURES)
        self.assertEqual(status_ids, MODULE.REQUIRED_FEATURES)

    def test_incomplete_stage_cannot_report_pass(self):
        audit = MODULE.Audit()
        MODULE.audit_source(audit)
        result = audit.result()
        self.assertEqual(result['status'], 'NEEDS_REVIEW')
        joined = '\n'.join(result['errors'])
        self.assertIn('not yet implemented/validated', joined)

    def test_legacy_client_is_outside_workspace(self):
        self.assertFalse((ROOT / 'Leno').exists())
        self.assertEqual(ROOT.name, 'VancedIOS')


if __name__ == '__main__':
    unittest.main()
