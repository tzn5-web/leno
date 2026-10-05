#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXPECTED_HOST_BUNDLE_ID = "com.google.ios.youtube"


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class IPAInfo:
    ipa: Path
    app_root: str
    info: dict
    executable_member: str
    executable_name: str


def fail(message: str) -> None:
    raise ValidationError(message)


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read manifest {path}: {exc}")
    if not isinstance(data, dict):
        fail("manifest root must be a JSON object")
    return data


def inspect_ipa(ipa: Path) -> IPAInfo:
    if not ipa.is_file() or ipa.stat().st_size <= 0:
        fail(f"IPA missing or empty: {ipa}")
    if not zipfile.is_zipfile(ipa):
        fail(f"not a valid ZIP/IPA: {ipa}")

    with zipfile.ZipFile(ipa) as zf:
        info_members = []
        for name in zf.namelist():
            parts = name.split("/")
            if (
                len(parts) == 3
                and parts[0] == "Payload"
                and parts[1].endswith(".app")
                and parts[2] == "Info.plist"
            ):
                info_members.append(name)

        if len(info_members) != 1:
            fail(
                "expected exactly one Payload/*.app/Info.plist, "
                f"found {len(info_members)}"
            )

        info_member = info_members[0]
        app_root = info_member[: -len("Info.plist")]
        try:
            info = plistlib.loads(zf.read(info_member))
        except Exception as exc:
            fail(f"cannot parse host Info.plist: {exc}")
        if not isinstance(info, dict):
            fail("Info.plist root must be a dictionary")

        executable_name = str(info.get("CFBundleExecutable") or "").strip()
        if not executable_name:
            fail("Info.plist missing CFBundleExecutable")
        executable_member = app_root + executable_name
        try:
            entry = zf.getinfo(executable_member)
        except KeyError:
            fail(f"main executable missing from IPA: {executable_member}")
        if entry.file_size <= 0:
            fail("main executable is empty")

    return IPAInfo(
        ipa=ipa,
        app_root=app_root,
        info=info,
        executable_member=executable_member,
        executable_name=executable_name,
    )


def run_checked(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        fail(f"required validation tool is unavailable: {args[0]}")
    if proc.returncode != 0:
        fail(
            f"{' '.join(args)} failed with exit {proc.returncode}: "
            f"{proc.stdout.strip()}"
        )
    return proc.stdout


def extract_executable(info: IPAInfo, destination: Path) -> None:
    with zipfile.ZipFile(info.ipa) as zf:
        with zf.open(info.executable_member) as src, destination.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    destination.chmod(0o755)


def macho_arches(executable: Path) -> set[str]:
    output = run_checked(["lipo", "-archs", str(executable)])
    arches = {token.strip() for token in output.strip().split() if token.strip()}
    if not arches:
        fail("lipo returned no architectures")
    return arches


def macho_cryptids(executable: Path) -> list[int]:
    output = run_checked(["otool", "-l", str(executable)])
    values = [
        int(value)
        for value in re.findall(
            r"^\s*cryptid\s+(\d+)\s*$",
            output,
            flags=re.MULTILINE,
        )
    ]
    if not values:
        fail(
            "main executable has no LC_ENCRYPTION_INFO cryptid field; "
            "expected a decrypted App Store Mach-O"
        )
    return values


def macho_dependencies(executable: Path) -> list[str]:
    output = run_checked(["otool", "-L", str(executable)])
    deps = []
    for line in output.splitlines()[1:]:
        candidate = line.strip().split(" (", 1)[0].strip()
        if candidate:
            deps.append(candidate)
    return deps


def dylib_basenames(ipa: Path) -> set[str]:
    with zipfile.ZipFile(ipa) as zf:
        return {
            Path(name).name
            for name in zf.namelist()
            if name.lower().endswith(".dylib") and not name.endswith("/")
        }


def require_background_modes(info: dict, required: Iterable[str]) -> None:
    modes = info.get("UIBackgroundModes", [])
    if isinstance(modes, str):
        modes = [modes]
    if not isinstance(modes, list):
        fail("UIBackgroundModes is not an array")
    missing = [mode for mode in required if mode not in modes]
    if missing:
        fail("required UIBackgroundModes missing: " + ", ".join(missing))


def validate_common(
    ipa_info: IPAInfo,
    manifest: dict,
) -> tuple[set[str], list[int], list[str]]:
    validation = manifest.get("host_validation", {})
    required_arches = set(validation.get("required_arches", ["arm64"]))
    required_modes = validation.get("required_background_modes", ["audio"])

    with tempfile.TemporaryDirectory(prefix="vancedios-ipa-audit-") as temp:
        executable = Path(temp) / ipa_info.executable_name
        extract_executable(ipa_info, executable)
        arches = macho_arches(executable)
        cryptids = macho_cryptids(executable)
        deps = macho_dependencies(executable)

    missing_arches = sorted(required_arches - arches)
    if missing_arches:
        fail(
            "host executable missing required architectures: "
            + ", ".join(missing_arches)
        )
    if validation.get("require_decrypted", True) and any(
        value != 0 for value in cryptids
    ):
        fail("host executable is still encrypted (cryptid != 0)")

    require_background_modes(ipa_info.info, required_modes)
    return arches, cryptids, deps


def validate_host(ipa: Path, manifest: dict) -> dict:
    info = inspect_ipa(ipa)
    arches, cryptids, deps = validate_common(info, manifest)

    target = manifest.get("target", {})
    expected_version = str(target.get("tested_youtube_version") or "")
    bundle_id = str(info.info.get("CFBundleIdentifier") or "")
    version = str(info.info.get("CFBundleShortVersionString") or "")

    if bundle_id != EXPECTED_HOST_BUNDLE_ID:
        fail(
            f"host bundle id must be {EXPECTED_HOST_BUNDLE_ID}, "
            f"got {bundle_id or '<empty>'}"
        )
    if not expected_version:
        fail("manifest target.tested_youtube_version is empty")
    if version != expected_version:
        fail(
            f"host YouTube version must be exactly tested version "
            f"{expected_version}, got {version or '<empty>'}"
        )

    return {
        "mode": "host",
        "ipa": str(ipa),
        "bundle_id": bundle_id,
        "version": version,
        "display_name": info.info.get("CFBundleDisplayName")
        or info.info.get("CFBundleName"),
        "minimum_os": info.info.get("MinimumOSVersion"),
        "architectures": sorted(arches),
        "cryptids": cryptids,
        "background_modes": info.info.get("UIBackgroundModes", []),
        "dependency_count": len(deps),
        "status": "PASS",
    }


def validate_output(
    ipa: Path,
    manifest: dict,
    expected_bundle_id: str,
    expected_display_name: str | None,
) -> dict:
    info = inspect_ipa(ipa)
    arches, cryptids, deps = validate_common(info, manifest)

    target = manifest.get("target", {})
    expected_version = str(target.get("tested_youtube_version") or "")
    bundle_id = str(info.info.get("CFBundleIdentifier") or "")
    version = str(info.info.get("CFBundleShortVersionString") or "")
    display_name = str(
        info.info.get("CFBundleDisplayName")
        or info.info.get("CFBundleName")
        or ""
    )

    if bundle_id != expected_bundle_id:
        fail(
            f"output bundle id mismatch: expected {expected_bundle_id}, "
            f"got {bundle_id or '<empty>'}"
        )
    if expected_display_name is not None and display_name != expected_display_name:
        fail(
            f"output display name mismatch: expected "
            f"{expected_display_name!r}, got {display_name!r}"
        )
    if version != expected_version:
        fail(
            f"output YouTube version changed: expected {expected_version}, "
            f"got {version or '<empty>'}"
        )

    required_dylibs = manifest.get("payload", {}).get("required_dylibs", [])
    present = dylib_basenames(ipa)
    missing_files = [name for name in required_dylibs if name not in present]
    if missing_files:
        fail(
            "output IPA missing injected dylibs: "
            + ", ".join(missing_files)
        )

    dep_basenames = {Path(dep).name for dep in deps}
    missing_load_commands = [
        name for name in required_dylibs if name not in dep_basenames
    ]
    if missing_load_commands:
        fail(
            "main executable missing LC_LOAD_DYLIB references: "
            + ", ".join(missing_load_commands)
        )

    return {
        "mode": "output",
        "ipa": str(ipa),
        "bundle_id": bundle_id,
        "version": version,
        "display_name": display_name,
        "minimum_os": info.info.get("MinimumOSVersion"),
        "architectures": sorted(arches),
        "cryptids": cryptids,
        "background_modes": info.info.get("UIBackgroundModes", []),
        "required_dylibs": required_dylibs,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strict VancedIOS host/output IPA validator"
    )
    parser.add_argument("mode", choices=["host", "output"])
    parser.add_argument("ipa", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "manifest.json",
    )
    parser.add_argument("--bundle-id", default=EXPECTED_HOST_BUNDLE_ID)
    parser.add_argument("--display-name")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
        if args.mode == "host":
            report = validate_host(args.ipa, manifest)
        else:
            report = validate_output(
                args.ipa,
                manifest,
                args.bundle_id,
                args.display_name,
            )
    except ValidationError as exc:
        print(f"VANCEDIOS IPA VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
