import importlib.util
import plistlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
here = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("security", here / "security_scan.py")
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)
class SecurityScanTests(unittest.TestCase):
    def test_unknown_candidate_is_always_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"sample.ipa"
            cmd=struct.pack("<6I",0x2c,24,0,0,0,0)
            macho=struct.pack("<8I",0xfeedfacf,0x100000c,0,2,1,24,0,0)+cmd
            with zipfile.ZipFile(f,"w") as z:
                z.writestr("Payload/YouTube.app/Info.plist",plistlib.dumps({
                    "CFBundleIdentifier":"com.google.ios.youtube",
                    "CFBundleShortVersionString":"21.40.5",
                    "CFBundleExecutable":"YouTube",
                    "NSCameraUsageDescription":"Video"
                }))
                z.writestr("Payload/YouTube.app/YouTube",macho)
            r=security.scan(f)
            self.assertEqual(r["risk_status"],"QUARANTINE_UNVERIFIED_ORIGIN")
            self.assertFalse(r["official_google_binary_match"])
            self.assertFalse(r["pinned_candidate_hash_matches"])
            self.assertEqual(r["extension_count"],0)
