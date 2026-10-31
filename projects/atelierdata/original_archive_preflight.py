"""Read-only integrity and Windows dependency preflight for owner-provided ZIP parts.

No extraction, PE execution, registry changes, driver installs or license modifications.
Requires the original INVENTAR.json (with SHA256 for every ZIP entry).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

PART_RE = re.compile(r"autodata_part_[0-9]{4}\.zip\Z")
HEX64_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
CHUNK_SIZE = 1024 * 1024
PE_LIMIT = 32 * 1024 * 1024
# Mandatory exclusion at the lowest-level archive reader; cannot be overridden.
BLOCKED_PACKAGE = "autodata_part_0016.zip"


def safe_path(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return False
    parts = value.split("/")
    return not value.startswith("/") and all(x not in ("", ".", "..") for x in parts)


def load_manifest(path: Path) -> tuple[dict, dict]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ValueError("Manifest must contain a files array")
    entries = {}
    names = set()
    for file in manifest["files"]:
        name = file.get("path")
        if not safe_path(name) or not name.startswith("Autodata__3.45/") or name in names:
            raise ValueError("Unsafe or duplicate manifest file path")
        names.add(name)
        chunks = file.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("Missing chunks")
        total = 0
        for chunk in chunks:
            package, entry = chunk.get("package"), chunk.get("entry")
            size, digest = chunk.get("bytes"), chunk.get("sha256")
            if (not isinstance(package, str) or not PART_RE.fullmatch(package)
                or not safe_path(entry) or not entry.startswith("Autodata__3.45/")
                or type(size) is not int or size < 0 or not isinstance(digest, str)
                or not HEX64_RE.fullmatch(digest)):
                raise ValueError("Invalid chunk metadata")
            key = (package, entry)
            if key in entries:
                raise ValueError("Duplicate package entry")
            entries[key] = {"file": name, "size": size, "sha256": digest.lower()}
            total += size
        if type(file.get("size_bytes")) is not int or total != file["size_bytes"]:
            raise ValueError("Chunk sizes do not match file size")
    return manifest, entries


def _u16(buf: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(buf):
        raise ValueError("Truncated PE")
    return struct.unpack_from("<H", buf, offset)[0]


def _u32(buf: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(buf):
        raise ValueError("Truncated PE")
    return struct.unpack_from("<I", buf, offset)[0]


def inspect_pe(binary: bytes) -> dict:
    """Parse PE import descriptor names only; never load or execute the binary."""
    if len(binary) < 0x100 or binary[:2] != b"MZ":
        raise ValueError("Not a DOS/PE executable")
    pe = _u32(binary, 0x3c)
    if pe + 24 > len(binary) or binary[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE signature")
    machine, sections, opt_size = _u16(binary, pe + 4), _u16(binary, pe + 6), _u16(binary, pe + 20)
    opt = pe + 24
    if sections > 96 or opt + opt_size > len(binary):
        raise ValueError("Invalid PE headers")
    magic = _u16(binary, opt)
    if magic not in (0x10b, 0x20b):
        raise ValueError("Unsupported PE optional header")
    dd = opt + (96 if magic == 0x10b else 112)
    if dd + 16 > opt + opt_size:
        raise ValueError("Missing PE import directory")
    import_rva = _u32(binary, dd + 8)
    import_size = _u32(binary, dd + 12)
    sections_list = []
    for i in range(sections):
        sec = opt + opt_size + i * 40
        if sec + 40 > len(binary):
            raise ValueError("Truncated PE sections")
        sections_list.append((_u32(binary, sec + 12),
                              max(_u32(binary, sec + 8), _u32(binary, sec + 16)),
                              _u32(binary, sec + 20), _u32(binary, sec + 16)))

    def rva_offset(rva: int) -> int:
        for virtual, span, raw, raw_size in sections_list:
            if virtual <= rva < virtual + span and rva - virtual < raw_size:
                offset = raw + rva - virtual
                if offset >= len(binary):
                    break
                return offset
        raise ValueError("Import RVA is outside file-backed sections")

    imports = []
    if import_rva:
        start = rva_offset(import_rva)
        for i in range(min(512, (import_size or 10240) // 20 + 1)):
            at = start + 20 * i
            if at + 20 > len(binary):
                raise ValueError("Truncated PE import descriptor")
            if binary[at:at + 20] == bytes(20):
                break
            name_rva = _u32(binary, at + 12)
            if not name_rva:
                raise ValueError("Import descriptor without DLL name")
            name_at = rva_offset(name_rva)
            end = binary.find(b"\0", name_at, min(len(binary), name_at + 260))
            if end < 0:
                raise ValueError("Unterminated PE import name")
            imports.append(binary[name_at:end].decode("ascii", errors="replace"))
        else:
            raise ValueError("Unterminated import descriptor table")
    return {"machine": f"0x{machine:04x}", "format": "PE32" if magic == 0x10b else "PE32+",
            "subsystem": _u16(binary, opt + 68), "imported_dlls": sorted(set(imports), key=str.lower),
            "sentinel_dll_literal_present": b"SentinelKeyW.DLL" in binary,
            "literal_is_runtime_dependency_proof": False}


def audit(manifest_path: Path, parts_dir: Path) -> dict:
    manifest, expected = load_manifest(manifest_path)
    parts_dir = Path(parts_dir).resolve(strict=True)
    if not parts_dir.is_dir():
        raise ValueError("Parts path must be a directory")
    packages = sorted({key[0] for key in expected})
    errors = []
    missing = []
    matched = 0
    verified_entries = set()
    captured = {}
    for package in packages:
        if package == BLOCKED_PACKAGE:
            # Do not stat, open, parse or extract the malware-flagged package.
            # Its mere presence does not authorize inspection.
            missing.append(package)
            continue
        file = parts_dir / package
        if not file.is_file() or file.is_symlink():
            missing.append(package)
            continue
        try:
            with zipfile.ZipFile(file) as z:
                infos = z.infolist()
                counts = collections.Counter(i.filename for i in infos if not i.is_dir())
                if any(n > 1 for n in counts.values()):
                    errors.append(f"{package}: duplicate ZIP entries")
                    continue
                expected_names = {entry for (p, entry) in expected if p == package}
                extra = set(counts) - expected_names
                if extra:
                    errors.append(f"{package}: {len(extra)} unexpected entries")
                for entry in expected_names:
                    meta = expected[(package, entry)]
                    info = z.getinfo(entry) if entry in counts else None
                    if info is None or info.file_size != meta["size"]:
                        errors.append(f"{package}: missing/size mismatch: {entry}")
                        continue
                    h = hashlib.sha256()
                    count = 0
                    keep = entry.endswith("/ADBCD.exe") or entry.endswith("/VERINFO.DAT")
                    if keep and info.file_size > PE_LIMIT:
                        raise ValueError("PE/metadata capture exceeds bound")
                    content = bytearray() if keep else None
                    with z.open(info) as stream:
                        while True:
                            chunk = stream.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            count += len(chunk)
                            if count > meta["size"]:
                                raise ValueError("Decompressed entry exceeds manifest size")
                            h.update(chunk)
                            if keep:
                                content.extend(chunk)
                    if count != meta["size"] or h.hexdigest() != meta["sha256"]:
                        errors.append(f"{package}: SHA256 mismatch: {entry}")
                        continue
                    matched += 1
                    verified_entries.add((package, entry))
                    if keep:
                        captured[entry] = bytes(content)
        except (OSError, zipfile.BadZipFile, RuntimeError, KeyError, ValueError) as exc:
            errors.append(f"{package}: {type(exc).__name__}: {str(exc)[:180]}")
    all_idf = {file["path"] for file in manifest["files"] if file["path"].lower().endswith(".idf")}
    file_chunks = collections.defaultdict(set)
    for key, meta in expected.items():
        file_chunks[meta["file"]].add(key)
    complete_idf = {name for name in all_idf if file_chunks[name] <= verified_entries}
    missing_idf = sorted(all_idf - complete_idf)
    pe = None
    for entry, data in captured.items():
        if entry.endswith("/ADBCD.exe"):
            try:
                pe = inspect_pe(data)
            except ValueError as exc:
                errors.append(f"PE parsing failed: {exc}")
    version = {}
    for entry, data in captured.items():
        if entry.endswith("/VERINFO.DAT"):
            for line in data.decode("latin-1", errors="replace").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() in {"ProductCode", "VersionNo", "ExpiryDate"}:
                        version[key.strip()] = value.strip()
    expected_package_count = manifest.get("package_count")
    return {"schema": "atelierdata-original-preflight-v1",
            "manifest_file_count": len(manifest["files"]), "expected_chunk_count": len(expected),
            "verified_chunk_count": matched, "expected_package_count": expected_package_count,
            "available_package_count": len(packages) - len(missing), "missing_packages": missing,
            "idf_file_count": len(all_idf), "verified_idf_file_count": len(complete_idf),
            "missing_chunk_count": len(expected) - matched,
            "unverified_idf_files": missing_idf, "errors": errors,
            "pe": pe, "version_metadata": version,
            "data_integrity": "PASS" if not missing_idf else "INCOMPLETE",
            "complete_archive": not missing and not errors and matched == len(expected),
            "original_executed": False, "license_verified": False,
            "runtime_compatibility_verified": False, "idf_decoded": False,
            "note": "PE imports and literal strings do not prove runtime load paths; missing licensed components cannot be bypassed."}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--parts-dir", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = audit(args.manifest, args.parts_dir)
    report = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    print(report)
    return 0 if result["complete_archive"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
