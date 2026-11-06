"""Read-only SHA-256 integrity gate for explicitly authorized static-analysis samples.

No original content, filename, path or hash is printed or uploaded.
The caller supplies the expected SHA-256 from a trusted private manifest.
"""
import hashlib
import os
from pathlib import Path

CHUNK_BYTES = 1024 * 1024


def verify_local_sample(path, expected_sha256, *, max_bytes=1024 * 1024 * 1024):
    """Return minimal aggregate evidence; reject symlinks and changing files.

    This does not authorize use of a file and never executes its contents.
    """
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("Expected a 64-character SHA-256 digest")
    try:
        int(expected_sha256, 16)
    except ValueError as exc:
        raise ValueError("Invalid SHA-256 digest") from exc
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("Invalid byte limit")
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("Not a regular, non-symlink file")
    before = p.stat()
    if before.st_size > max_bytes:
        raise ValueError("Sample exceeds size limit")
    digest = hashlib.sha256()
    count = 0
    # O_NOFOLLOW protects against a symlink substitution on supporting OSes.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(p, flags)
    try:
        opened = os.fstat(fd)
        if not os.path.samestat(before, opened):
            raise ValueError("Sample changed before opening")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while True:
                chunk = stream.read(min(CHUNK_BYTES, max_bytes - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > max_bytes:
                    raise ValueError("Sample exceeds size limit")
                digest.update(chunk)
        after = os.fstat(fd)
        if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Sample changed during hashing")
    finally:
        os.close(fd)
    return {"schema": "atelierdata-private-integrity-v1",
            "sample_bytes": count,
            "sha256_matches_expected": digest.hexdigest().lower() == expected_sha256.lower(),
            "source_executed": False, "idf_decoder_proven": False}
