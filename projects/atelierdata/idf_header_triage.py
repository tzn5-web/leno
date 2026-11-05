"""Read-only, bounded IDF sample triage. Never executes or decodes input.

Only use with files the operator is authorized to inspect. Output is aggregate
metadata; no file bytes, strings, offsets or proprietary records are emitted.
"""
import argparse
import hashlib
import json
import math
import os
import stat
from pathlib import Path

MAX_SAMPLE = 65536
MAX_FILE = 1024 * 1024 * 1024


def inspect(path: Path, expected_sha256: str, sample_size: int = MAX_SAMPLE) -> dict:
    if not 1 <= sample_size <= MAX_SAMPLE:
        raise ValueError("sample_size outside safe bound")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256.lower()):
        raise ValueError("expected SHA256 required")
    initial = path.lstat()
    if not stat.S_ISREG(initial.st_mode):
        raise ValueError("regular non-symlink file required")
    size = initial.st_size
    if size > MAX_FILE:
        raise ValueError("file too large for bounded triage")
    digest = hashlib.sha256()
    sample = bytearray()
    bytes_read = 0
    # O_NOFOLLOW closes the check/open symlink race on platforms that support it.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_size != size or
                (before.st_dev, before.st_ino) != (initial.st_dev, initial.st_ino)):
            raise ValueError("source changed before triage read")
        while chunk := stream.read(1024 * 1024):
            bytes_read += len(chunk)
            if bytes_read > MAX_FILE:
                raise ValueError("file grew beyond safe bound during triage")
            digest.update(chunk)
            if len(sample) < sample_size:
                sample.extend(chunk[:sample_size - len(sample)])
        after = os.fstat(stream.fileno())
        final = path.lstat()
        if (bytes_read != size or after.st_size != size or final.st_size != size or
                (final.st_dev, final.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError("file size changed during triage")
        # Windows st_ctime is creation time and can be reported with
        # differing precision between fstat() and lstat(). Identity, size,
        # mtime and the caller-provided full-file SHA256 remain mandatory.
        # POSIX ctime additionally detects metadata/inode changes.
        ctime_changed = (
            os.name != "nt" and
            (before.st_ctime_ns != after.st_ctime_ns or
             before.st_ctime_ns != final.st_ctime_ns)
        )
        if (before.st_mtime_ns != after.st_mtime_ns or
                before.st_mtime_ns != final.st_mtime_ns or
                ctime_changed or before.st_ino != after.st_ino):
            raise ValueError("source changed during triage")
    if digest.hexdigest() != expected_sha256.lower():
        raise ValueError("SHA256 mismatch")
    counts = [0] * 256
    for byte in sample:
        counts[byte] += 1
    n = len(sample)
    entropy = -sum((v / n) * math.log2(v / n) for v in counts if v) if n else 0.0
    return {
        "sha256_verified": True,
        "size_bytes": size,
        "sample_bytes": n,
        "sample_entropy_bits_per_byte": round(entropy, 4),
        "sample_zero_fraction": round(counts[0] / n, 6) if n else 0,
        "sample_printable_ascii_fraction": round(sum(counts[32:127]) / n, 6) if n else 0,
        "format_identified": False,
        "decoder_verified": False,
        "caution": "Entropy and byte frequencies cannot establish encryption, compression, schema, or licensing.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.file.resolve():
        parser.error("output cannot overwrite input")
    report = inspect(args.file, args.expected_sha256)
    # Exclusive creation prevents replacing an existing report or following an output symlink.
    # Keep the source file untouched even if a caller supplies an existing output path.
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        parser.error(f"output already exists: {args.output}")


if __name__ == "__main__":
    main()
