"""Strict read-only integrity gate for a private, partially unavailable Autodata distribution.

Only authorized ZIPs are opened; the malware-flagged part_0016 is NEVER opened.
This is not a repair, installer, decoder, entitlement check, or authenticity test.
The public JSON contains counts and status, never original file contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from original_archive_preflight import audit, load_manifest

DEFAULT_BLOCKED = ("autodata_part_0016.zip",)
SCHEMA = "atelierdata-original-integrity-gate-v1"


def assess(manifest_path: Path, parts_dir: Path,
           blocked_packages: tuple[str, ...] = DEFAULT_BLOCKED) -> dict:
    manifest_path = Path(manifest_path)
    parts_dir = Path(parts_dir).resolve(strict=True)
    if not parts_dir.is_dir():
        raise ValueError("Parts directory must exist")
    manifest, expected = load_manifest(manifest_path)
    packages = {package for package, _ in expected}
    declared_count = manifest.get("package_count")
    if declared_count is not None and declared_count != len(packages):
        raise ValueError("Manifest package_count disagrees with package entries")
    if len(manifest["files"]) != len({row["path"] for row in manifest["files"]}):
        raise ValueError("Duplicate manifest file paths")

    blocked = set(blocked_packages)
    if any(not name.startswith("autodata_part_") or
           not name.endswith(".zip") or "/" in name or "\\" in name
           for name in blocked):
        raise ValueError("Invalid blocked package name")
    # Explicit fail-closed behavior: do not even let the underlying preflight
    # open a flagged ZIP if somebody later places it in the directory.
    present_blocked = sorted(name for name in blocked
                             if (parts_dir / name).exists() or
                             (parts_dir / name).is_symlink())
    if present_blocked:
        raise ValueError("Blocked package present; refuse inspection: " +
                         ", ".join(present_blocked))

    result = audit(manifest_path, parts_dir)
    missing = set(result["missing_packages"])
    expected_present = sum(package not in missing for package, _ in expected)
    verified_present = result["verified_chunk_count"]
    errors = result["errors"]
    unexpected_missing = sorted(missing - blocked)
    count_mismatch = verified_present != expected_present
    if errors or count_mismatch:
        state = "INTEGRITY_FAILURE"
    elif unexpected_missing:
        state = "UNEXPECTED_MISSING_PACKAGES"
    elif missing:
        state = "AVAILABLE_PARTS_VERIFIED_DISTRIBUTION_INCOMPLETE"
    else:
        state = "ALL_DISTRIBUTION_PARTS_INTEGRITY_VERIFIED"

    main = "Autodata__3.45/ADCDA2/ADBCD.exe"
    main_chunks = [key for key, row in expected.items() if row["file"] == main]
    main_verified = (bool(main_chunks) and not errors and not count_mismatch
                     and all(key[0] not in missing for key in main_chunks)
                     and result["pe"] is not None)
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "schema": SCHEMA,
        "manifest_sha256": manifest_digest,
        "manifest_files": len(manifest["files"]),
        "expected_packages": len(packages),
        "available_packages": len(packages - missing),
        "unavailable_packages": sorted(missing),
        "explicitly_blocked_packages": sorted(blocked & packages),
        "unexpected_unavailable_packages": unexpected_missing,
        "expected_chunks_in_available_packages": expected_present,
        "sha256_verified_chunks_in_available_packages": verified_present,
        "total_expected_chunks": len(expected),
        "idf_total": result["idf_file_count"],
        "idf_sha256_verified": result["verified_idf_file_count"],
        "main_executable_sha256_and_pe_verified": main_verified,
        "errors": errors,
        "state": state,
        "original_executed": False,
        "installer_executed": False,
        "licensing_proven": False,
        "publisher_authenticity_proven": False,
        "windows_runtime_tested": False,
        "idf_decoded": False,
        "installation_ready": False,
        "interpretation": (
            "SHA256 matches the owner-supplied manifest, not the vendor signature. "
            "An intact partial archive does not establish a usable or licensed "
            "Windows installation. The blocked package was never opened."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--parts-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--blocked-package", action="append",
                        help="Explicitly excluded ZIP; defaults to part_0016")
    args = parser.parse_args()
    blocked = tuple(args.blocked_package) if args.blocked_package else DEFAULT_BLOCKED
    try:
        report = assess(args.manifest, args.parts_dir, blocked)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Avoid printing raw private archive contents on failures.
        print(json.dumps({"schema": SCHEMA, "state": "PRECONDITION_FAILED",
                          "error_type": type(exc).__name__,
                          "error": str(exc)[:240]}, ensure_ascii=False))
        return 2
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["state"] in (
        "AVAILABLE_PARTS_VERIFIED_DISTRIBUTION_INCOMPLETE",
        "ALL_DISTRIBUTION_PARTS_INTEGRITY_VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
