"""Synthetic-only tests for the Windows installer signature gate."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from original_windows_authenticode_gate import (
    BLOCKED_NAME, POWERSHELL, assess, evaluate_signature,
    normalize_hex, read_windows_signature, validate_path,
)

GOOD_THUMBPRINT = "A" * 40
GOOD_SUBJECT = "CN=Authorized Vendor"
SIGNED = {
    "status": "Valid", "signature_type": "Authenticode",
    "thumbprint": GOOD_THUMBPRINT, "subject": GOOD_SUBJECT,
}


def sample_file(folder, name="authorized_vendor.exe"):
    path = Path(folder) / name
    path.write_bytes(b"MZ" + b"INERT-SYNTHETIC-UNSIGNED-TEST")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


class WindowsSignatureGateTests(unittest.TestCase):
    def test_exact_valid_signer_is_only_signature_acceptance(self):
        result = evaluate_signature(SIGNED, GOOD_THUMBPRINT, GOOD_SUBJECT)
        self.assertEqual(result["state"], "SIGNATURE_MATCHES_SUPPLIED_EXPECTATIONS")

    def test_wrong_thumbprint_rejected(self):
        result = evaluate_signature(SIGNED, "B" * 40)
        self.assertEqual(result["state"], "SIGNATURE_NOT_ACCEPTED")

    def test_wrong_subject_rejected(self):
        result = evaluate_signature(SIGNED, GOOD_THUMBPRINT, "CN=Someone Else")
        self.assertEqual(result["state"], "SIGNATURE_NOT_ACCEPTED")

    def test_unsigned_rejected_even_if_thumbprint_present(self):
        result = evaluate_signature({**SIGNED, "status": "NotSigned"}, GOOD_THUMBPRINT)
        self.assertEqual(result["state"], "SIGNATURE_NOT_ACCEPTED")

    def test_missing_certificate_rejected(self):
        result = evaluate_signature({"status": "Valid"}, GOOD_THUMBPRINT)
        self.assertEqual(result["state"], "SIGNATURE_NOT_ACCEPTED")

    def test_hash_mismatch_does_not_inspect_signature(self):
        with tempfile.TemporaryDirectory() as d:
            path, _ = sample_file(d)
            reader = Mock(side_effect=AssertionError("Must not be called"))
            result = assess(path, "0" * 64, GOOD_THUMBPRINT, signature_reader=reader)
            self.assertEqual(result["state"], "HASH_MISMATCH")
            reader.assert_not_called()

    def test_hash_and_signature_match_but_not_license(self):
        with tempfile.TemporaryDirectory() as d:
            path, digest = sample_file(d)
            result = assess(path, digest, GOOD_THUMBPRINT, GOOD_SUBJECT,
                            signature_reader=lambda _: SIGNED)
            self.assertEqual(result["state"], "SIGNATURE_MATCHES_SUPPLIED_EXPECTATIONS")
            self.assertFalse(result["license_entitlement_verified"])
            self.assertFalse(result["vendor_provenance_independently_verified"])
            self.assertFalse(result["installation_authorized_by_this_tool"])
            self.assertFalse(result["target_executed"])
            self.assertNotIn(str(Path(d)), str(result))

    def test_mutation_during_signature_probe_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path, digest = sample_file(d)
            def mutate(candidate):
                candidate.write_bytes(b"CHANGED")
                return SIGNED
            result = assess(path, digest, GOOD_THUMBPRINT, signature_reader=mutate)
            self.assertEqual(result["state"], "FILE_CHANGED_DURING_INSPECTION")

    def test_invalid_digest_input(self):
        with self.assertRaises(ValueError):
            normalize_hex("not-a-hash", 64)
        with self.assertRaises(ValueError):
            normalize_hex("A" * 39, 40)

    def test_blocked_package_refused_before_any_read(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / BLOCKED_NAME
            path.write_bytes(b"DO-NOT-INSPECT")
            with self.assertRaisesRegex(ValueError, "Blocked package"):
                validate_path(path)

    def test_unapproved_extension_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "unknown.zip"
            path.write_bytes(b"INERT")
            with self.assertRaisesRegex(ValueError, "EXE/DLL/MSI"):
                validate_path(path)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path, _ = sample_file(d)
            alias = Path(d) / "alias.exe"
            try:
                alias.symlink_to(path)
            except OSError:
                self.skipTest("Symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "symlink"):
                validate_path(alias)

    def test_path_is_never_inserted_into_powershell_code(self):
        self.assertIn("Get-AuthenticodeSignature -LiteralPath", POWERSHELL)
        self.assertIn("$env:ATELIERDATA_SIGNATURE_TARGET", POWERSHELL)
        self.assertNotIn("Invoke-Expression", POWERSHELL)
        self.assertNotIn("Start-Process", POWERSHELL)

    @unittest.skipUnless(os.name == "nt", "Windows system trust test")
    def test_windows_powershell_binary_ignores_untrusted_path(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "powershell.exe"
            fake.write_bytes(b"FAKE-DO-NOT-RUN")
            response = SimpleNamespace(returncode=0, stdout='{"status":"NotSigned"}')
            with patch.dict(os.environ, {"PATH": d}):
                with patch("original_windows_authenticode_gate.subprocess.run",
                           return_value=response) as invoke:
                    read_windows_signature(Path(d) / "dummy.exe")
            command = invoke.call_args.args[0]
            expected = (Path(os.environ["SystemRoot"]) / "System32" /
                        "WindowsPowerShell" / "v1.0" / "powershell.exe")
            self.assertEqual(Path(command[0]), expected)
            self.assertNotEqual(Path(command[0]), fake)

    @unittest.skipUnless(os.name == "nt", "Windows native trust test")
    def test_windows_native_unsigned_fixture_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            path, digest = sample_file(d, "inert_unsigned.exe")
            result = assess(path, digest, GOOD_THUMBPRINT)
            self.assertNotEqual(result["state"], "SIGNATURE_MATCHES_SUPPLIED_EXPECTATIONS")
            self.assertFalse(result["installation_authorized_by_this_tool"])


if __name__ == "__main__":
    unittest.main()
