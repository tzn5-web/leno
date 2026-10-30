#!/usr/bin/env python3
"""Stage a *licensed* Autodata 3.45 vendor payload for an Inno Setup installer.

This is a file copier and consistency checker, not an activator.
It never executes any file from the supplied application folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def load_allowlist(path: Path) -> list[dict]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    files = manifest["files"]
    if not files:
        raise ValueError("Empty allowlist")
    seen = set()
    for row in files:
        raw = row["path"]
        if not isinstance(raw, str):
            raise ValueError("Non-string allowlist path")
        rel = PurePosixPath(raw)
        if ("\\" in raw or ":" in raw
                or rel.is_absolute() or ".." in rel.parts or not rel.parts
                or rel.parts[0] != "ADCDA2"):
            raise ValueError("Unsafe or out-of-scope path: " + str(raw))
        if not isinstance(row["size_bytes"], int) or row["size_bytes"] < 0:
            raise ValueError("Invalid file size: " + raw)
        key = raw.casefold()
        if key in seen:
            raise ValueError("Duplicate path: " + raw)
        seen.add(key)
    if "adcda2/adbcd.exe" not in seen:
        raise ValueError("Missing main vendor executable in allowlist")
    return files


def resolve_source(path: Path) -> Path:
    source = path.expanduser().resolve(strict=True)
    if source.name.lower() == "adcda2":
        source = source.parent
    if not (source / "ADCDA2").is_dir():
        raise FileNotFoundError("Expected an ADCDA2 folder inside --source")
    return source


def check_regular_file(source: Path, rel: PurePosixPath) -> Path:
    candidate = source
    for part in rel.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Symlink refused: " + str(candidate))
    if not candidate.is_file():
        raise FileNotFoundError(str(candidate))
    if not candidate.resolve(strict=True).is_relative_to(source):
        raise ValueError("Path escapes source: " + str(candidate))
    return candidate


def sha256_copy(src: Path, dst: Path | None) -> str:
    h = hashlib.sha256()
    if dst is None:
        with src.open("rb") as inp:
            for chunk in iter(lambda: inp.read(4 * 1024 * 1024), b""):
                h.update(chunk)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with src.open("rb") as inp, dst.open("xb") as out:
            for chunk in iter(lambda: inp.read(4 * 1024 * 1024), b""):
                h.update(chunk)
                out.write(chunk)
    return h.hexdigest()


def stage(source: Path, destination: Path, allowlist: list[dict], dry_run: bool) -> dict:
    source = resolve_source(source)
    destination = destination.expanduser().resolve(strict=False)
    if destination == source or source in destination.parents:
        raise ValueError("Destination must not be inside the source")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Destination must be empty: " + str(destination))
    verified = []
    # Validate the *entire* inventory before writing anything.
    for row in allowlist:
        rel = PurePosixPath(row["path"])
        src = check_regular_file(source, rel)
        actual_size = src.stat().st_size
        if actual_size != row["size_bytes"]:
            raise ValueError(
                "Size mismatch for %s: expected %d, got %d"
                % (rel, row["size_bytes"], actual_size)
            )
        verified.append((row, src))
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
    output = []
    for row, src in verified:
        dest = None if dry_run else destination.joinpath(*PurePosixPath(row["path"]).parts)
        digest = sha256_copy(src, dest)
        output.append({"path": row["path"], "size_bytes": row["size_bytes"],
                       "sha256": digest})
    result = {
        "status": "DRY_RUN_PASS" if dry_run else "STAGED_PASS",
        "source_file_count": len(output),
        "total_bytes": sum(r["size_bytes"] for r in output),
        "files": output,
        "provenance_verified": False,
        "licensing_verified": False,
        "warning": "Hash/size consistency does not prove safety or a valid license.",
    }
    if not dry_run:
        (destination / "staged_sha256.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path,
                        help="Root containing ADCDA2, or the ADCDA2 directory")
    parser.add_argument("--staging", required=True, type=Path,
                        help="New/empty output folder, outside source")
    parser.add_argument("--allowlist", type=Path,
                        default=Path(__file__).with_name("payload-allowlist.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = stage(args.source, args.staging, load_allowlist(args.allowlist), args.dry_run)
    except (ValueError, FileNotFoundError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("STAGING_FAILED: " + str(exc), file=sys.stderr)
        return 2
    print("%s files=%d bytes=%d" %
          (result["status"], result["source_file_count"], result["total_bytes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
