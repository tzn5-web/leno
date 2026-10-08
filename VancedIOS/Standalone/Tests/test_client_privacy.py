import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == 'darwin', 'requires native Foundation runtime')
class ClientPrivacyTests(unittest.TestCase):
    def compile_and_run(self, name, sources):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / name
            subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-fblocks', '-framework', 'Foundation',
                            *[str(ROOT / s) for s in sources], '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, check=True, timeout=15)
            self.assertIn('PASS', result.stdout)

    def test_local_premium_flags_and_dynamic_latest_version(self):
        self.compile_and_run('client_checks', ['VClientPolicy.m', 'Tests/client_checks.m'])

    def test_telemetry_acknowledgement_preserves_auth_and_media_routes(self):
        self.compile_and_run('privacy_checks', ['Tests/privacy_checks.m'])
