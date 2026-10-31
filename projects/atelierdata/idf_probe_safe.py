"""Bounded, read-only IDF inventory probe for owner-authorized files.

No decoding, decompression to disk, execution, or DRM interaction. ZIP entries
are streamed and SHA256-checked; samples never leave the local report.
The returned SHA256 is a computed digest, not a comparison to an owner-provided
expected digest. Use an independent trusted manifest to verify provenance.
"""
from __future__ import annotations

import collections
import hashlib
import math
import stat
import zipfile
from pathlib import Path, PurePosixPath
from idf_stride_evidence import strongest_stride

SAMPLE_BYTES = 65536
MAX_IDF_FILES = 256
MAX_ZIP_ENTRIES = 4096
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 10000


def _entry_name(name):
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise ValueError("Unsafe ZIP entry name")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in (".", "..") for part in name.split("/")):
        raise ValueError("Unsafe ZIP entry path")
    if ":" in name.split("/")[0]:
        raise ValueError("Windows drive path forbidden")
    return path


def _read_digest(stream, declared_size):
    if not 0 <= declared_size <= MAX_FILE_BYTES:
        raise ValueError("IDF member exceeds size limit")
    digest = hashlib.sha256()
    sample = bytearray()
    total = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > declared_size or total > MAX_FILE_BYTES:
            raise ValueError("IDF size exceeds declared limit")
        digest.update(chunk)
        if len(sample) < SAMPLE_BYTES:
            sample.extend(chunk[:SAMPLE_BYTES - len(sample)])
    if total != declared_size:
        raise ValueError("IDF member size mismatch")
    return digest.hexdigest(), bytes(sample)


def _summarize(name, size, digest, sample):
    if not sample:
        entropy = 0.0
    else:
        counts = collections.Counter(sample)
        entropy = -sum((n / len(sample)) * math.log2(n / len(sample)) for n in counts.values())
    motif = strongest_stride(sample)
    return {"name": name, "bytes": size, "sha256_computed": digest,
            "sampled_bytes": len(sample), "sample_entropy": round(entropy, 4),
            "header_hex": sample[:16].hex(), "motif_run_count": motif["count"] if motif else 0,
            "motif_stride_bytes": motif["stride"] if motif else None,
            "motif_start_offset": motif["start"] if motif else None,
            "decoded": False}


def probe_idf(root):
    """Inspect local .IDF files or ZIP members; fail closed on unsafe inputs."""
    root = Path(root)
    if root.is_symlink():
        raise ValueError("Symbolic link input forbidden")
    items = []
    total_bytes = 0
    if root.is_file() and root.suffix.lower() == ".zip":
        with zipfile.ZipFile(root) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_ENTRIES:
                raise ValueError("Too many ZIP members")
            seen = set()
            for member in members:
                name = _entry_name(member.filename)
                canonical = member.filename.casefold()
                if canonical in seen:
                    raise ValueError("Duplicate ZIP member name")
                seen.add(canonical)
                mode = (member.external_attr >> 16) & 0xffff
                if stat.S_IFMT(mode) == stat.S_IFLNK:
                    raise ValueError("ZIP symlink forbidden")
                if member.is_dir() or name.suffix.lower() != ".idf":
                    continue
                if member.flag_bits & 1:
                    raise ValueError("Encrypted ZIP member unsupported")
                if member.file_size > MAX_FILE_BYTES:
                    raise ValueError("IDF member exceeds size limit")
                if member.file_size > 0 and member.file_size / max(1, member.compress_size) > MAX_COMPRESSION_RATIO:
                    raise ValueError("Excessive ZIP compression ratio")
                total_bytes += member.file_size
                if total_bytes > MAX_TOTAL_BYTES or len(items) >= MAX_IDF_FILES:
                    raise ValueError("IDF probe resource limit exceeded")
                with archive.open(member) as stream:
                    digest, sample = _read_digest(stream, member.file_size)
                items.append(_summarize(member.filename, member.file_size, digest, sample))
    elif root.is_file() and root.suffix.casefold() == ".idf":
        # Single-file inspection avoids forcing users to copy private evidence
        # into a new directory or ZIP. Read-only, with the same resource limits.
        size = root.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError("IDF file exceeds size limit")
        with root.open("rb") as stream:
            digest, sample = _read_digest(stream, size)
        total_bytes = size
        items.append(_summarize(root.name, size, digest, sample))
    elif root.is_dir():
        base = root.resolve(strict=True)
        for path in root.rglob("*"):
            if path.suffix.lower() != ".idf":
                continue
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(base):
                raise ValueError("Unsafe IDF path")
            size = path.stat().st_size
            total_bytes += size
            if total_bytes > MAX_TOTAL_BYTES or len(items) >= MAX_IDF_FILES:
                raise ValueError("IDF probe resource limit exceeded")
            with path.open("rb") as stream:
                digest, sample = _read_digest(stream, size)
            items.append(_summarize(path.relative_to(root).as_posix(), size, digest, sample))
    else:
        raise ValueError("Choose an existing directory or ZIP")
    items.sort(key=lambda item: item["name"].casefold())
    return {"schema": "atelierdata-idf-probe-v2", "count": len(items),
            "total_idf_bytes_hashed": total_bytes, "samples": items,
            "target_executed": False, "idf_decoder_proven": False,
            "warning": "Computed SHA256 values are not provenance verification without a trusted reference. Format IDF is NOT decoded."}
