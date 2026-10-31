"""Read-only ZIP metadata integrity gate for owner-authorized original parts.

No decompression, extraction, execution, licensing, CRC or payload SHA256 claims.
autodata_part_0016.zip is never accessed, even when present locally.
"""
import argparse
import json
import os
import re
import stat
import struct
import zipfile
from pathlib import Path, PurePosixPath

BLOCKED_PACKAGE = "autodata_part_0016.zip"
LOCAL = struct.Struct("<IHHHHHIIIHH")
MAX_ZIP = 512 * 1024 * 1024
MAX_MEMBER = 512 * 1024 * 1024


def safe_name(name):
    return (isinstance(name, str) and bool(name) and "\\" not in name
            and "\0" not in name and ":" not in name and not name.startswith("/")
            and all(part not in ("", ".", "..") for part in name.split("/")))


def expected_parts(manifest):
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ValueError("Invalid manifest")
    result = {}
    for row in manifest["files"]:
        for c in row["chunks"]:
            pkg, name, size = c["package"], c["entry"], c["bytes"]
            if not re.fullmatch(r"autodata_part_[0-9]{4}\.zip", pkg) or not safe_name(name):
                raise ValueError("Unsafe manifest path")
            if not isinstance(size, int) or size < 0 or size > MAX_MEMBER:
                raise ValueError("Invalid declared member size")
            entries = result.setdefault(pkg, {})
            if name in entries:
                raise ValueError("Duplicate manifest entry")
            entries[name] = size
    for entries in result.values():
        names = [name.casefold() for name in entries]
        if len(names) != len(set(names)):
            raise ValueError("Case-insensitive manifest collision")
    if BLOCKED_PACKAGE not in result:
        raise ValueError("Blocked package not declared: distribution mismatch")
    return result


def check_zip(path, expected):
    errors = set()
    try:
        if path.is_symlink():
            return {"status": "rejected", "errors": ["symlink_package"]}
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as source:
            meta = os.fstat(source.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_ZIP:
                return {"status": "rejected", "errors": ["unsafe_package_type_or_size"]}
            with zipfile.ZipFile(source) as z:
                infos = z.infolist()
                if len(infos) > 10000:
                    return {"status": "rejected", "errors": ["too_many_members"]}
                seen, ranges = set(), []
                for info in infos:
                    name = info.filename
                    if not safe_name(name) or name.endswith("/"):
                        errors.add("unsafe_or_directory_member")
                        continue
                    folded = name.casefold()
                    if folded in seen:
                        errors.add("duplicate_casefold_member")
                    seen.add(folded)
                    if name not in expected:
                        errors.add("unexpected_member")
                    elif info.file_size != expected[name]:
                        errors.add("manifest_size_mismatch")
                    if info.flag_bits & 1:
                        errors.add("encrypted_member")
                    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        errors.add("unsupported_compression")
                    if info.create_system == 3 and stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                        errors.add("symlink_member")
                    if info.file_size > MAX_MEMBER or info.compress_size < 0:
                        errors.add("member_size_out_of_bounds")
                    if info.file_size > 1048576 and info.file_size > 1000 * max(1, info.compress_size):
                        errors.add("suspicious_expansion_ratio")
                    start = info.header_offset
                    if start < 0 or start + LOCAL.size > meta.st_size:
                        errors.add("local_header_out_of_bounds")
                        continue
                    source.seek(start)
                    header = source.read(LOCAL.size)
                    if len(header) != LOCAL.size:
                        errors.add("truncated_local_header")
                        continue
                    sig, _, local_flags, method, _, _, _, _, _, nlen, xlen = LOCAL.unpack(header)
                    if sig != 0x04034B50 or local_flags != info.flag_bits or method != info.compress_type:
                        errors.add("local_header_mismatch")
                        continue
                    data_start = start + LOCAL.size + nlen + xlen
                    data_end = data_start + info.compress_size
                    if data_end > meta.st_size or data_end > z.start_dir or data_start < start:
                        errors.add("compressed_data_out_of_bounds")
                        continue
                    raw_name = source.read(nlen)
                    try:
                        local_name = raw_name.decode("utf-8" if local_flags & 0x800 else "cp437")
                    except UnicodeDecodeError:
                        local_name = None
                    if local_name != name:
                        errors.add("local_name_mismatch")
                    ranges.append((start, data_end))
                if set(expected) != {i.filename for i in infos}:
                    errors.add("manifest_member_set_mismatch")
                ordered = sorted(ranges)
                if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
                    errors.add("overlapping_local_member_ranges")
                return {"status": "rejected" if errors else "verified_structure_only",
                        "errors": sorted(errors), "members": len(infos),
                        "declared_uncompressed_bytes": sum(i.file_size for i in infos)}
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, struct.error) as e:
        return {"status": "rejected", "errors": ["zip_read_error:" + type(e).__name__]}


def audit(manifest, parts_dir):
    expected = expected_parts(manifest)
    parts_dir = Path(parts_dir)
    if not parts_dir.is_dir():
        raise ValueError("Parts directory missing")
    results = {}
    for pkg in sorted(expected):
        if pkg == BLOCKED_PACKAGE:
            results[pkg] = {"status": "blocked_not_accessed"}
            continue
        path = parts_dir / pkg
        if path.is_symlink():
            results[pkg] = {"status": "rejected", "errors": ["symlink_package"]}
        elif not path.is_file():
            results[pkg] = {"status": "missing"}
        else:
            results[pkg] = check_zip(path, expected[pkg])
    counts = {s: sum(v["status"] == s for v in results.values())
              for s in ("verified_structure_only", "rejected", "missing", "blocked_not_accessed")}
    return {"schema": "atelierdata-zip-container-audit-v1", "counts": counts,
            "packages": results, "original_executed": False,
            "payloads_decompressed": False, "sha256_verified_by_this_audit": False,
            "license_verified": False, "blocked_package_accessed": False,
            "limitation": "ZIP central/local metadata only, not CRC, SHA256, authenticity, installer or Windows runtime."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--parts-dir", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = audit(json.loads(args.manifest.read_text(encoding="utf-8")), args.parts_dir)
    result = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        if args.output.resolve() in (args.manifest.resolve(), (args.parts_dir / BLOCKED_PACKAGE).resolve()):
            raise ValueError("Refusing to overwrite source")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Refusing to overwrite existing report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            f.write(result)
    print(result)
    return 2 if report["counts"]["rejected"] or report["counts"]["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
