import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == 'darwin', 'requires native Security/Foundation runtime')
class IdentityTests(unittest.TestCase):
    def test_native_oauth_callback_is_preserved_with_distinct_os_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'identity_checks'
            subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-fblocks', '-framework', 'Foundation',
                            '-framework', 'Security', str(ROOT / 'VUpdatePolicy.m'),
                            str(ROOT / 'VClientPolicy.m'), str(ROOT / 'VPrivacy.m'),
                            str(ROOT / 'Tests/identity_checks.m'), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
            self.assertIn('PASS', result.stdout)
