"""Read-only PE certificate-table evidence for the owner's original distribution.

Checks five allowlisted PE files in authorized ZIP parts against the owner's
SHA256 manifest. Never loads executable code, checks license state or inspects
the malware-flagged part_0016. A PKCS#7 container is NOT signature validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from original_archive_preflight import load_manifest

SCHEMA = "atelierdata-original-pe-certificates-v1"
ROOT = "Autodata__3.45/ADCDA2/"
ALLOWED = ("ADBCD.exe", "ChilkatCert.dll", "ChilkatCrypt2.dll",
           "ChilkatUtil.dll", "RelLic.dll")
BLOCKED = "autodata_part_0016.zip"
MAX_PE = 32 * 1024 * 1024
READ_SIZE = 1024 * 1024


def _u16(data: bytes, off: int) -> int:
    if off < 0 or off + 2 > len(data):
        raise ValueError("Truncated PE header")
    return struct.unpack_from("<H", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise ValueError("Truncated PE header")
    return struct.unpack_from("<I", data, off)[0]


def inspect_certificate_table(data: bytes) -> dict:
    """Parse WIN_CERTIFICATE boundaries, not cryptographic validity."""
    if len(data) < 128 or data[:2] != b"MZ":
        raise ValueError("Invalid DOS signature")
    pe = _u32(data, 0x3c)
    if pe > len(data) - 24 or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE signature")
    opt_size = _u16(data, pe + 20)
    opt = pe + 24
    if opt + opt_size > len(data):
        raise ValueError("Optional header exceeds file")
    magic = _u16(data, opt)
    if magic == 0x10b:
        number_offset, directory_offset, pe_format = 92, 96, "PE32"
    elif magic == 0x20b:
        number_offset, directory_offset, pe_format = 108, 112, "PE32+"
    else:
        raise ValueError("Unsupported optional header")
    if number_offset + 4 > opt_size:
        raise ValueError("Missing NumberOfRvaAndSizes")
    n_dirs = _u32(data, opt + number_offset)
    if n_dirs < 5:
        return {"pe_format": pe_format, "certificate_table": "absent",
                "win_certificate_count": 0, "pkcs7_container_count": 0,
                "authenticode_verified": False}
    if directory_offset + 5 * 8 > opt_size:
        raise ValueError("Security directory outside optional header")
    cert_off = _u32(data, opt + directory_offset + 4 * 8)
    cert_size = _u32(data, opt + directory_offset + 4 * 8 + 4)
    if not cert_off and not cert_size:
        return {"pe_format": pe_format, "certificate_table": "absent",
                "win_certificate_count": 0, "pkcs7_container_count": 0,
                "authenticode_verified": False}
    if not cert_off or not cert_size or cert_off % 8:
        raise ValueError("Malformed certificate directory offset/size")
    if cert_off > len(data) or cert_size > len(data) - cert_off:
        raise ValueError("Certificate directory outside file")
    at, end = cert_off, cert_off + cert_size
    count = pkcs7_count = 0
    while at < end:
        if end - at < 8:
            raise ValueError("Truncated WIN_CERTIFICATE header")
        length = _u32(data, at)
        revision = _u16(data, at + 4)
        cert_type = _u16(data, at + 6)
        if length < 8 or length > end - at:
            raise ValueError("Invalid WIN_CERTIFICATE length")
        if revision not in (0x100, 0x200):
            raise ValueError("Invalid WIN_CERTIFICATE revision")
        if cert_type == 0x0002:
            pkcs7_count += 1
        aligned = (length + 7) & ~7
        if aligned > end - at:
            raise ValueError("WIN_CERTIFICATE padding outside directory")
        at += aligned
        count += 1
    return {"pe_format": pe_format, "certificate_table": "present",
            "win_certificate_count": count, "pkcs7_container_count": pkcs7_count,
            "authenticode_verified": False}


def _verified_member(archive_path: Path, entry: str, expected_size: int,
                     expected_sha256: str) -> bytes:
    with zipfile.ZipFile(archive_path) as archive:
        members = [info for info in archive.infolist() if info.filename == entry]
        if len(members) != 1 or members[0].is_dir():
            raise ValueError("Missing or duplicate allowlisted ZIP member")
        if members[0].file_size != expected_size or expected_size > MAX_PE:
            raise ValueError("Invalid PE size")
        digest = hashlib.sha256()
        data = bytearray()
        with archive.open(members[0]) as stream:
            while True:
                part = stream.read(READ_SIZE)
                if not part:
                    break
                if len(data) + len(part) > expected_size:
                    raise ValueError("ZIP decompression exceeds manifest size")
                digest.update(part)
                data.extend(part)
        if len(data) != expected_size or digest.hexdigest() != expected_sha256.lower():
            raise ValueError("PE SHA256 mismatch against owner manifest")
        return bytes(data)


def assess(manifest_path: Path, parts_dir: Path) -> dict:
    """Only five known available root PE files; fail closed on blocked ZIP."""
    manifest, _ = load_manifest(Path(manifest_path))
    root = Path(parts_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Parts path is not a directory")
    if (root / BLOCKED).exists() or (root / BLOCKED).is_symlink():
        raise ValueError("Blocked package present: refuse to inspect distribution")
    rows = {row["path"]: row for row in manifest["files"]}
    components = {}
    for name in ALLOWED:
        path = ROOT + name
        if path not in rows:
            raise ValueError("Allowlisted PE missing from manifest: " + name)
        row = rows[path]
        if len(row["chunks"]) != 1:
            raise ValueError("Expected one ZIP member per allowlisted PE")
        chunk = row["chunks"][0]
        package = chunk["package"]
        if package == BLOCKED:
            raise ValueError("Allowlisted PE is in blocked package")
        file = root / package
        if not file.is_file() or file.is_symlink():
            raise ValueError("Required authorized package missing: " + package)
        if chunk["bytes"] != row["size_bytes"]:
            raise ValueError("Inconsistent PE size in manifest")
        binary = _verified_member(file, chunk["entry"], chunk["bytes"], chunk["sha256"])
        evidence = inspect_certificate_table(binary)
        components[name] = {
            "sha256_verified_against_owner_manifest": True,
            "sha256": chunk["sha256"].lower(), "size_bytes": len(binary), **evidence,
        }
    return {
        "schema": SCHEMA,
        "verified_component_count": len(components),
        "components": components,
        "embedded_pkcs7_components": sum(
            v["pkcs7_container_count"] > 0 for v in components.values()),
        "unsigned_certificate_table_components": sum(
            v["certificate_table"] == "absent" for v in components.values()),
        "blocked_package_opened": False,
        "original_executed": False,
        "publisher_signature_cryptographically_verified": False,
        "vendor_provenance_verified": False,
        "license_entitlement_verified": False,
        "installation_ready": False,
        "note": ("A PKCS#7 WIN_CERTIFICATE container is not proof of a valid or trusted "
                 "Authenticode signature. A missing embedded certificate table "
                 "does not exclude external catalog signing."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.output and (args.output.exists() or
                            args.output.resolve() == args.manifest.resolve()):
            raise ValueError("Output already exists or aliases the manifest")
        report = assess(args.manifest, args.parts_dir)
        payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as out:
                out.write(payload)
        print(payload)
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "AUDIT_FAILED",
                          "error_type": type(exc).__name__}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
