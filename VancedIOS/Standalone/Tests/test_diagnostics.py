import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == 'darwin', 'requires native Foundation runtime')
class DiagnosticTests(unittest.TestCase):
    def test_error_report_retains_reason_without_credentials_and_stays_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / 'diagnostic_checks'
            subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-fblocks', '-framework', 'Foundation',
                            str(ROOT / 'VDiagnostics.m'), str(ROOT / 'Tests/diagnostic_checks.m'),
                            '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
            self.assertIn('PASS', result.stdout)
