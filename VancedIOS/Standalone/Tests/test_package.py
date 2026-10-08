import importlib.util
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('standalone_package', ROOT / 'package.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackageTests(unittest.TestCase):
    def test_identity_is_independent(self):
        original = plistlib.dumps({
            'CFBundleIdentifier': 'com.google.ios.youtube',
            'CFBundleURLTypes': [{'CFBundleURLSchemes': ['youtube', 'vnd.youtube']}],
            'LSApplicationQueriesSchemes': ['youtube', 'googlechrome'],
            'UIBackgroundModes': ['audio', 'remote-notification'],
        })
        config = {'bundle_id': 'ro.ion.youtubevanced', 'display_name': 'YouTube Vanced'}
        info = plistlib.loads(module.standalone_info(original, config))
        self.assertEqual(info['CFBundleIdentifier'], config['bundle_id'])
        self.assertEqual(info['CFBundleURLTypes'][0]['CFBundleURLSchemes'], ['youtubevanced', config['bundle_id']])
        self.assertNotIn('youtube', info['LSApplicationQueriesSchemes'])
        self.assertIn('audio', info['UIBackgroundModes'])

    @unittest.skipUnless(sys.platform == 'darwin', 'requires native codesign and CI-built modules')
    def test_stripped_modules_can_be_signed_and_verified(self):
        for name in module.LIBRARIES:
            with self.subTest(module=name), tempfile.TemporaryDirectory() as tmp:
                source = (ROOT / 'artifacts' / (name + '.dylib')).read_bytes()
                unsigned = module.unsigned_macho(source)
                self.assertFalse(any(c == 0x1d for c, _, _ in module.commands(unsigned)))
                path = Path(tmp) / (name + '.dylib')
                path.write_bytes(unsigned)
                subprocess.run(['codesign', '--force', '--sign', '-', str(path)], check=True)
                subprocess.run(['codesign', '--verify', '--strict', '--verbose=2', str(path)], check=True)

    @unittest.skipUnless(sys.platform == 'darwin', 'requires CI-built module')
    def test_rejects_encrypted_modules(self):
        data = bytearray((ROOT / 'artifacts/VancedIdentity.dylib').read_bytes())
        found = False
        for command, offset, raw in module.commands(data):
            if command == 0x2c:
                struct.pack_into('<I', data, offset + 16, 1)
                found = True
                break
        self.assertTrue(found)
        with self.assertRaisesRegex(ValueError, 'encrypted'):
            module.unsigned_macho(data)


if __name__ == '__main__':
    unittest.main()
