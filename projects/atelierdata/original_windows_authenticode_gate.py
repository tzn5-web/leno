"""Read-only Windows Authenticode gate for a separately obtained, authorized installer.

This is NOT an installer, malware scanner, license verifier, or Autodata decoder.
Never points at the malware-flagged autodata_part_0016.zip. The expected hash
and signer thumbprint must come from an independent, trusted vendor channel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

SCHEMA = "atelierdata-original-windows-authenticode-gate-v1"
BLOCKED_NAME = "autodata_part_0016.zip"
MAX_BYTES = 1024 * 1024 * 1024
CHUNK = 1024 * 1024
ALLOWED_EXTENSIONS = {".exe", ".dll", ".msi"}

# No file path is interpolated into this static PowerShell program. In
# particular, quote/wildcard characters in a filename cannot become commands.
POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$s = Get-AuthenticodeSignature -LiteralPath $env:ATELIERDATA_SIGNATURE_TARGET
$c = $s.SignerCertificate
[pscustomobject]@{
    status = [string]$s.Status
    signature_type = [string]$s.SignatureType
    thumbprint = $(if ($null -ne $c) { [string]$c.Thumbprint } else { '' })
    subject = $(if ($null -ne $c) { [string]$c.Subject } else { '' })
} | ConvertTo-Json -Compress -Depth 3
"""


def normalize_hex(value: str, length: int) -> str:
    result = value.replace(":", "").replace(" ", "").upper()
    if len(result) != length or not re.fullmatch(r"[0-9A-F]+", result):
        raise ValueError("Expected a hexadecimal digest of exactly " + str(length) + " digits")
    return result


def validate_path(candidate: Path) -> Path:
    path = Path(candidate).absolute()
    if any(part.casefold() == BLOCKED_NAME for part in path.parts):
        raise ValueError("Blocked package must never be inspected")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Only external EXE/DLL/MSI files may be checked")
    # Refuse junctions and symlinks, including those in parent directories.
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("Reparse point or symlink is not accepted")
    if not path.is_file():
        raise ValueError("Candidate must be an existing regular file")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Candidate exceeds static inspection size limit")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest().upper()


def read_windows_signature(path: Path) -> dict:
    """Use Windows trust APIs via PowerShell; never invoke the target file."""
    if os.name != "nt":
        raise RuntimeError("Authenticode trust verification requires Windows")
    shell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if shell is None:
        raise RuntimeError("PowerShell is not available")
    env = os.environ.copy()
    env["ATELIERDATA_SIGNATURE_TARGET"] = str(path)
    run = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", POWERSHELL],
        env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    if run.returncode != 0:
        raise RuntimeError("Windows signature inspection returned an error")
    # Do not include raw stderr or private filesystem paths in public reports.
    try:
        result = json.loads(run.stdout.strip())
    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Invalid Windows signature response") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Invalid Windows signature response type")
    return result


def evaluate_signature(signature: dict, expected_thumbprint: str,
                       expected_subject: str | None = None) -> dict:
    """Pure policy evaluation; unit tests do not need a real certificate."""
    status = str(signature.get("status", ""))
    observed = str(signature.get("thumbprint", "")).replace(" ", "").upper()
    subject = str(signature.get("subject", ""))
    thumbprint_matches = observed == expected_thumbprint
    subject_matches = expected_subject is None or subject == expected_subject
    trusted_status = status == "Valid"
    accepted = trusted_status and thumbprint_matches and subject_matches
    return {
        "signature_status": status,
        "signature_type": str(signature.get("signature_type", "")),
        "observed_signer_thumbprint": observed,
        "observed_signer_subject": subject,
        "windows_signature_status_valid": trusted_status,
        "signer_thumbprint_matches_independent_expectation": thumbprint_matches,
        "signer_subject_matches_expectation": subject_matches,
        "state": "SIGNATURE_MATCHES_SUPPLIED_EXPECTATIONS" if accepted
                 else "SIGNATURE_NOT_ACCEPTED",
    }


def assess(candidate: Path, expected_sha256: str, expected_thumbprint: str,
           expected_subject: str | None = None, signature_reader=None) -> dict:
    expected_hash = normalize_hex(expected_sha256, 64)
    expected_signer = normalize_hex(expected_thumbprint, 40)
    path = validate_path(candidate)
    size = path.stat().st_size
    digest = sha256_file(path)
    report = {
        "schema": SCHEMA, "file_name": path.name, "file_size_bytes": size,
        "expected_sha256": expected_hash, "observed_sha256": digest,
        "sha256_matches_independent_expectation": digest == expected_hash,
        "target_executed": False, "installer_executed": False,
        "license_entitlement_verified": False, "vendor_provenance_independently_verified": False,
        "installation_authorized_by_this_tool": False,
        "idf_decoded": False,
        "state": "HASH_MISMATCH",
    }
    # A bad hash never reaches Windows trust inspection.
    if digest != expected_hash:
        return report
    if signature_reader is None:
        signature_reader = read_windows_signature
    try:
        signature = signature_reader(path)
        # Detect any file modification during Windows signature inspection.
        if path.stat().st_size != size or sha256_file(path) != expected_hash:
            report["state"] = "FILE_CHANGED_DURING_INSPECTION"
            return report
        report.update(evaluate_signature(signature, expected_signer, expected_subject))
    except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError):
        report["state"] = "WINDOWS_SIGNATURE_INSPECTION_UNAVAILABLE"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-signer-thumbprint", required=True,
                        help="SHA1 certificate thumbprint from independent vendor evidence")
    parser.add_argument("--expected-signer-subject",
                        help="Optional exact certificate subject from vendor evidence")
    parser.add_argument("--output", type=Path, help="New JSON report path (never overwrite)")
    args = parser.parse_args()
    try:
        if args.output:
            if args.output.exists() or args.output.absolute() == args.candidate.absolute():
                raise ValueError("Output must be a new path, never the candidate")
        report = assess(args.candidate, args.expected_sha256,
                        args.expected_signer_thumbprint, args.expected_signer_subject)
        if args.output:
            # Exclusive creation; never overwrite an existing file.
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    except (ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "state": "PRECONDITION_FAILED",
                          "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["state"] == "SIGNATURE_MATCHES_SUPPLIED_EXPECTATIONS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
