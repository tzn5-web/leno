import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == 'darwin', 'requires native Objective-C Foundation runtime')
class GuestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temporary.name) / 'guest_checks'
        subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-fblocks', '-framework', 'Foundation',
                        str(ROOT / 'VGuestEntry.m'), str(ROOT / 'VGuestStore.m'),
                        str(ROOT / 'Tests/guest_checks.m'), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_case(self, name):
        with tempfile.TemporaryDirectory() as data:
            result = subprocess.run([str(self.binary), name, data], check=True, capture_output=True, text=True)
            self.assertIn('PASS', result.stdout)

    def test_native_guest_transaction(self):
        self.run_case('transaction')

    def test_progress_flood_is_throttled(self):
        self.run_case('progress')

    def test_native_guest_history_enabled_once(self):
        self.run_case('native-history')

    def test_history_favorites_and_playlists_survive_reload(self):
        self.run_case('persistence')

    def test_corrupt_library_is_preserved(self):
        self.run_case('corruption')
