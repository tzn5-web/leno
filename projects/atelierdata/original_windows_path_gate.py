"""Read-only Windows pathname compatibility audit for an owner-provided inventory.

Only parses text/JSON metadata. It never opens ZIP packages or executable payloads.
The report intentionally contains aggregate counts, not private file names.
"""
from __future__ import annotations
import argparse
import collections
import json
import re
import unicodedata
from pathlib import Path

SCHEMA = "atelierdata-windows-path-gate-v1"
ROOT = "Autodata__3.45"
INVALID = re.compile(r'[<>:"\\\\|?*\\x00-\\x1f]')
RESERVED = re.compile(r'^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\\..*)?$', re.I)
LINE = re.compile(r'^\\s*(\\d+)\\s+(.+?)\\s*$')

def load_paths(inventory: Path) -> list[tuple[str, int]]:
    inventory = Path(inventory)
    if inventory.suffix.lower() == ".json":
        data = json.loads(inventory.read_text(encoding="utf-8-sig"))
        rows = data.get("files") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise ValueError("JSON must contain a files list")
        result = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str) or type(row.get("size_bytes")) is not int:
                raise ValueError("Invalid manifest row")
            result.append((row["path"], row["size_bytes"]))
        return result
    if inventory.suffix.lower() != ".txt":
        raise ValueError("Only TXT inventory or JSON manifest is supported")
    result = []
    for line in inventory.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        match = LINE.fullmatch(line)
        if match is None:
            raise ValueError("Invalid inventory line")
        result.append((match.group(2), int(match.group(1))))
    return result

def audit_paths(rows: list[tuple[str, int]], max_relative_utf16: int = 240) -> dict:
    if not isinstance(max_relative_utf16, int) or not 32 <= max_relative_utf16 <= 32767:
        raise ValueError("Invalid path length limit")
    issues = collections.Counter()
    seen: set[str] = set()
    total = 0
    idfs = 0
    for name, size in rows:
        if not isinstance(name, str) or type(size) is not int or size < 0:
            raise ValueError("Invalid inventory entry")
        total += size
        idfs += name.lower().endswith(".idf")
        parts = name.split("/")
        if not name or name.startswith("/") or len(parts) < 2 or parts[0] != ROOT or any(not p or p in (".", "..") for p in parts):
            issues["unsafe_relative_path"] += 1
        if any(INVALID.search(part) for part in parts):
            issues["invalid_windows_character"] += 1
        if any(part.endswith((".", " ")) for part in parts):
            issues["trailing_dot_or_space"] += 1
        if any(RESERVED.fullmatch(part) for part in parts):
            issues["reserved_windows_device_name"] += 1
        if len(name.encode("utf-16-le")) // 2 > max_relative_utf16:
            issues["long_relative_path"] += 1
        key = unicodedata.normalize("NFC", name).casefold()
        if key in seen:
            issues["windows_casefold_collision"] += 1
        seen.add(key)
    return {
        "schema": SCHEMA,
        "file_count": len(rows),
        "total_declared_bytes": total,
        "idf_file_count": idfs,
        "max_relative_utf16_limit": max_relative_utf16,
        "issues": dict(sorted(issues.items())),
        "state": "WINDOWS_PATH_NAMES_COMPATIBLE" if not issues else "WINDOWS_PATH_NAMES_NEED_REVIEW",
        "archive_bytes_read": 0,
        "blocked_package_opened": False,
        "executables_executed": False,
        "license_proven": False,
        "publisher_authenticity_proven": False,
        "original_installation_ready": False,
        "idf_decoded": False,
        "note": "Path-name screening only; does not verify SHA256, content, license, or Windows runtime. Casefold is a conservative Unicode approximation of Windows filename equality."
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = audit_paths(load_paths(args.inventory))
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\\n"
        if args.output:
            if args.output.resolve() == args.inventory.resolve():
                raise ValueError("Output must not overwrite input inventory")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        print(payload)
        return 0 if report["state"] == "WINDOWS_PATH_NAMES_COMPATIBLE" else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": SCHEMA, "state": "INPUT_INVALID", "error_type": type(exc).__name__}))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
