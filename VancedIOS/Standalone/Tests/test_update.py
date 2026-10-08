import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == 'darwin', 'requires native Objective-C Foundation runtime')
class UpdateTests(unittest.TestCase):
    def test_upgrade_suppression_preserves_completions(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'update_checks'
            subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-fblocks', '-framework', 'Foundation',
                            str(ROOT / 'VUpdatePolicy.m'), str(ROOT / 'Tests/update_checks.m'),
                            '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('PASS', result.stdout)
