"""Protect against presenting a wrapper package as verified Autodata 3.45."""
import sys, unittest, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class IdentityTests(unittest.TestCase):
    def test_wrapper_has_own_version_not_vendor_guess(self):
        text=(ROOT/"installer.iss").read_text(encoding="utf-8-sig")
        self.assertIn("AppVersion=0.1.0",text)
        self.assertIn("edition unverified",text)
        self.assertIn("DestDir: \"{app}\\ADCDA2\"",text)
        self.assertIn('WorkingDir: "{app}\\ADCDA2"',text)

    def test_no_installer_executes_binaries_or_changes_license_state(self):
        text=(ROOT/"installer.iss").read_text(encoding="utf-8-sig")
        for section in ("Run","Registry","Drivers"):
            self.assertIsNone(re.search(rf"^\\[{section}\\]\\s*$",text,re.M))

    def test_build_requires_private_review_and_real_manifest(self):
        text=(ROOT/"build.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("[Parameter(Mandatory = $true)][string]$ReviewRecord",text)
        self.assertIn("PRIVATE_REVIEW_RECORD_MUST_BE_OUTSIDE_REPOSITORY",text)
        self.assertIn("SOURCE_AND_LICENSE_REVIEW_INCOMPLETE",text)
        self.assertIn("verify_original_manifest.py",text)
        self.assertIn("DEFENDER_UNAVAILABLE",text)

if __name__=="__main__":unittest.main()
