"""Read-only fixed-stride motif evidence from SHA256-verified private IDF chunks.

Does not decode, extract, execute or export original IDF bytes. Aggregate
output contains counts, offsets and booleans only. Byte motifs stay in memory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

MAX_CHUNK = 128 * 1024 * 1024
MAX_SAMPLE = 256 * 1024
TOKEN_SIZE = 8
DEFAULT_NAMES = ("SGOPS.IDF", "SGINT.IDF", "FAS.IDF")


def strongest_stride(sample: bytes, min_repeats: int = 8):
    """Longest adjacent-occurrence run of an identical eight-byte token.

    Only constant strides from 12 through 128 bytes count. This does not
    establish compression, encryption, records or a decoding mechanism.
    """
    positions = defaultdict(list)
    for offset in range(max(0, len(sample) - TOKEN_SIZE + 1)):
        positions[sample[offset:offset + TOKEN_SIZE]].append(offset)
    best = None
    for token, offsets in positions.items():
        if len(offsets) < min_repeats:
            continue
        start = previous = offsets[0]
        stride = 0
        length = 1
        for offset in offsets[1:]:
            delta = offset - previous
            if delta == stride and 12 <= stride <= 128:
                length += 1
            else:
                if 12 <= stride <= 128 and length >= min_repeats and (
                        best is None or length > best["count"]):
                    best = dict(token=token, count=length, stride=stride,
                                start=start, end=previous)
                start, stride, length = previous, delta, 2
            previous = offset
        if 12 <= stride <= 128 and length >= min_repeats and (
                best is None or length > best["count"]):
            best = dict(token=token, count=length, stride=stride,
                        start=start, end=previous)
    return best


def first_verified_chunk(manifest, directory, name):
    candidates = [row for row in manifest["files"]
                  if row["path"].lower().endswith("/" + name.lower())]
    if len(candidates) != 1:
        raise ValueError("IDF name not unique in manifest: " + name)
    row = candidates[0]
    if not row["path"].lower().endswith(".idf") or not row.get("chunks"):
        raise ValueError("Invalid IDF inventory")
    chunk = row["chunks"][0]
    package = chunk["package"]
    if not re.fullmatch(r"autodata_part_\d{4}\.zip", package):
        raise ValueError("Unexpected ZIP package name")
    # Google Drive flagged this particular package; never open it, even when
    # a manifest points to it or its digest is known. No abuse bypass.
    if package.casefold() == "autodata_part_0016.zip":
        raise ValueError("Blocked package part_0016 must not be accessed")
    archive_path = directory / package
    if archive_path.is_symlink():
        raise ValueError("Symlink ZIP refused")
    expected_size = chunk["bytes"]
    if (type(expected_size) is not int or expected_size < 0 or
            expected_size > MAX_CHUNK):
        raise ValueError("Invalid or oversized chunk")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", chunk["sha256"]):
        raise ValueError("Invalid SHA256")
    checksum = hashlib.sha256()
    sample = bytearray()
    count = 0
    with zipfile.ZipFile(archive_path) as archive:
        entry = archive.getinfo(chunk["entry"])
        if entry.is_dir() or entry.file_size != expected_size:
            raise ValueError("ZIP member size mismatch")
        with archive.open(entry) as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                count += len(block)
                if count > expected_size:
                    raise ValueError("ZIP member exceeds declared size")
                checksum.update(block)
                if len(sample) < MAX_SAMPLE:
                    sample.extend(block[:MAX_SAMPLE - len(sample)])
    if count != expected_size or checksum.hexdigest() != chunk["sha256"].lower():
        raise ValueError("SHA256 mismatch for " + name)
    return bytes(sample), count


def analyze(manifest, directory, names=DEFAULT_NAMES):
    directory = Path(directory)
    evidence = {}
    private_tokens = {}
    for name in names:
        sample, count = first_verified_chunk(manifest, directory, name)
        run = strongest_stride(sample)
        evidence[name] = dict(first_chunk_sha256_verified=True,
                              first_chunk_bytes=count,
                              sampled_bytes=len(sample),
                              motif_run_count=run["count"] if run else 0,
                              motif_stride_bytes=run["stride"] if run else None,
                              motif_start_offset=run["start"] if run else None,
                              motif_end_offset=run["end"] if run else None)
        private_tokens[name] = run["token"] if run else None
    same_pair = ("SGOPS.IDF" in private_tokens and "SGINT.IDF" in private_tokens and
                 private_tokens["SGOPS.IDF"] is not None and
                 private_tokens["SGOPS.IDF"] == private_tokens["SGINT.IDF"])
    return dict(schema="atelierdata-idf-stride-aggregate-v1",
                analyzed_files=len(evidence), sample_limit_bytes=MAX_SAMPLE,
                target_executed=False, idf_decoder_proven=False,
                sgops_sgint_same_dominant_token=same_pair,
                files=evidence,
                interpretation="Fixed-stride byte repetitions are structural evidence only; not a format decoder.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.manifest.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Oversized manifest")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    result = analyze(manifest, args.parts_dir)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
