"""Synthetic tests for the private review gate; no original binaries or keys."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_gate import validate, ORIGINAL_RAR_SHA256, ORIGINAL_APP_SHA256, BUILD_REVIEWS, RELEASE_REVIEWS

def reviewed():
    result = {
        "original_rar_sha256": ORIGINAL_RAR_SHA256,
        "application_sha256": ORIGINAL_APP_SHA256,
        "reviewer": "Synthetic Test Reviewer",
        "reviewed_at_utc": "2026-10-31T08:00:00Z",
        "license_material_in_public_repo": False,
    }
    result.update({key:True for key in BUILD_REVIEWS})
    return result

class GateTests(unittest.TestCase):
    def test_no_approved_review_is_rejected(self):
        with self.assertRaises(ValueError):
            validate({"original_rar_sha256":ORIGINAL_RAR_SHA256}, "build")

    def test_valid_build_review(self):
        validate(reviewed(), "build")

    def test_missing_vendor_license_evidence_fails(self):
        obj=reviewed()
        obj["vendor_license_evidence_reviewed"]=False
        with self.assertRaisesRegex(ValueError,"vendor_license_evidence_reviewed"):
            validate(obj, "build")

    def test_version_discrepancy_review_is_required(self):
        obj=reviewed()
        obj["version_discrepancy_reviewed"]=False
        with self.assertRaisesRegex(ValueError,"version_discrepancy_reviewed"):
            validate(obj, "build")

    def test_installation_instructions_review_is_required(self):
        obj=reviewed()
        obj["installation_instructions_reviewed"]=False
        with self.assertRaisesRegex(ValueError,"installation_instructions_reviewed"):
            validate(obj, "build")

    def test_source_sha_changes_are_rejected(self):
        obj=reviewed()
        obj["application_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"REVIEW_APPLICATION_IDENTITY_MISMATCH"):
            validate(obj,"build")

    def test_license_content_must_stay_private(self):
        obj=reviewed()
        obj["license_material_in_public_repo"]=True
        with self.assertRaisesRegex(ValueError,"PRIVATE_LICENSE"):
            validate(obj,"build")

    def test_release_requires_real_windows_pass_and_signature(self):
        obj=reviewed()
        with self.assertRaises(ValueError):
            validate(obj, "release")
        obj.update({key:True for key in RELEASE_REVIEWS})
        validate(obj, "release")

if __name__=="__main__":
    unittest.main()
