from __future__ import annotations

import importlib.util
import json
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "Scripts" / "validate_ipa.py"
SPEC = importlib.util.spec_from_file_location("vancedios_validate_ipa", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def manifest() -> dict:
    return {
        "target": {
            "bundle_id": "com.google.ios.youtube",
            "tested_youtube_version": "21.18.4",
        },
        "host_validation": {
            "strict_version": True,
            "require_decrypted": True,
            "required_arches": ["arm64"],
            "required_background_modes": ["audio"],
        },
        "payload": {
            "required_dylibs": [
                "YouMod.dylib",
                "YTVideoOverlay.dylib",
                "YouPiP.dylib",
                "YTUHD.dylib",
                "YouTubeDislikesReturn.dylib",
                "VancedIOSCore.dylib",
            ]
        },
    }


def write_ipa(
    path: Path,
    *,
    bundle_id: str = "com.google.ios.youtube",
    version: str = "21.18.4",
    background_modes: list[str] | None = None,
    dylibs: list[str] | None = None,
    second_app: bool = False,
) -> None:
    info = {
        "CFBundleIdentifier": bundle_id,
        "CFBundleShortVersionString": version,
        "CFBundleExecutable": "YouTube",
        "CFBundleDisplayName": "YouTube",
        "UIBackgroundModes": background_modes
        if background_modes is not None
        else ["audio"],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Payload/YouTube.app/Info.plist", plistlib.dumps(info))
        zf.writestr("Payload/YouTube.app/YouTube", b"fake-mach-o")
        for dylib in dylibs or []:
            zf.writestr(f"Payload/YouTube.app/Frameworks/{dylib}", b"dylib")
        if second_app:
            other = dict(info)
            other["CFBundleIdentifier"] = "com.example.other"
            other["CFBundleExecutable"] = "Other"
            zf.writestr("Payload/Other.app/Info.plist", plistlib.dumps(other))
            zf.writestr("Payload/Other.app/Other", b"fake-mach-o")


class ValidateIPATests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="vancedios-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_inspect_rejects_multiple_top_level_apps(self) -> None:
        ipa = self.root / "multiple.ipa"
        write_ipa(ipa, second_app=True)
        with self.assertRaises(validator.ValidationError):
            validator.inspect_ipa(ipa)

    def test_host_accepts_exact_supported_decrypted_contract(self) -> None:
        ipa = self.root / "host.ipa"
        write_ipa(ipa)
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(validator, "macho_dependencies", return_value=[]),
        ):
            report = validator.validate_host(ipa, manifest())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["bundle_id"], "com.google.ios.youtube")
        self.assertEqual(report["version"], "21.18.4")

    def test_host_rejects_wrong_bundle(self) -> None:
        ipa = self.root / "wrong-bundle.ipa"
        write_ipa(ipa, bundle_id="com.example.youtube")
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(validator, "macho_dependencies", return_value=[]),
            self.assertRaises(validator.ValidationError),
        ):
            validator.validate_host(ipa, manifest())

    def test_host_rejects_wrong_version(self) -> None:
        ipa = self.root / "wrong-version.ipa"
        write_ipa(ipa, version="21.19.0")
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(validator, "macho_dependencies", return_value=[]),
            self.assertRaises(validator.ValidationError),
        ):
            validator.validate_host(ipa, manifest())

    def test_host_rejects_encrypted_binary(self) -> None:
        ipa = self.root / "encrypted.ipa"
        write_ipa(ipa)
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[1]),
            mock.patch.object(validator, "macho_dependencies", return_value=[]),
            self.assertRaises(validator.ValidationError),
        ):
            validator.validate_host(ipa, manifest())

    def test_host_rejects_missing_background_audio_mode(self) -> None:
        ipa = self.root / "no-background.ipa"
        write_ipa(ipa, background_modes=[])
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(validator, "macho_dependencies", return_value=[]),
            self.assertRaises(validator.ValidationError),
        ):
            validator.validate_host(ipa, manifest())

    def test_output_requires_every_dylib_and_load_command(self) -> None:
        ipa = self.root / "output.ipa"
        required = manifest()["payload"]["required_dylibs"]
        write_ipa(ipa, dylibs=required[:-1])

        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(
                validator,
                "macho_dependencies",
                return_value=[f"@rpath/{name}" for name in required],
            ),
            self.assertRaises(validator.ValidationError),
        ):
            validator.validate_output(
                ipa,
                manifest(),
                "com.google.ios.youtube",
                "YouTube",
            )

        write_ipa(ipa, dylibs=required)
        incomplete_loads = [f"@rpath/{name}" for name in required[:-1]]
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(
                validator,
                "macho_dependencies",
                return_value=incomplete_loads,
            ),
            self.assertRaises(validator.ValidationError),
        ):
            validator.validate_output(
                ipa,
                manifest(),
                "com.google.ios.youtube",
                "YouTube",
            )

    def test_output_accepts_complete_payload_and_load_commands(self) -> None:
        ipa = self.root / "output-pass.ipa"
        required = manifest()["payload"]["required_dylibs"]
        write_ipa(ipa, dylibs=required)
        with (
            mock.patch.object(validator, "macho_arches", return_value={"arm64"}),
            mock.patch.object(validator, "macho_cryptids", return_value=[0]),
            mock.patch.object(
                validator,
                "macho_dependencies",
                return_value=[f"@rpath/{name}" for name in required],
            ),
        ):
            report = validator.validate_output(
                ipa,
                manifest(),
                "com.google.ios.youtube",
                "YouTube",
            )
        self.assertEqual(report["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
