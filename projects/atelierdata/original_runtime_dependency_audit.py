"""Static, read-only PE dependency inventory for user-owned Autodata ZIP parts.

No extraction, binary execution, registry changes, installer invocation or license work.
A SHA256-verified inventory establishes integrity, not authenticity or authorization.
Only PE files immediately under ADCDA2 are inspected; all files are bounded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from original_archive_preflight import inspect_pe, load_manifest

MAX_PE_BYTES = 32 * 1024 * 1024
READ_CHUNK = 1024 * 1024
APP_ROOT = "Autodata__3.45/ADCDA2/"
WINDOWS_DLLS = {
    "ADVAPI32.DLL", "BCRYPT.DLL", "COMCTL32.DLL", "COMDLG32.DLL", "CRYPT32.DLL",
    "GDI32.DLL", "IMM32.DLL", "KERNEL32.DLL", "MSVCRT.DLL", "NTDLL.DLL",
    "OLE32.DLL", "OLEAUT32.DLL", "RPCRT4.DLL", "SHELL32.DLL", "SHLWAPI.DLL",
    "USER32.DLL", "VERSION.DLL", "WINMM.DLL", "WS2_32.DLL", "WINSPOOL.DRV",
    "SETUPAPI.DLL", "SECUR32.DLL", "PSAPI.DLL", "USERENV.DLL", "WININET.DLL",
}

def _root_pe_files(manifest: dict) -> dict[str, dict]:
    result = {}
    for row in manifest["files"]:
        name = row["path"]
        if not name.startswith(APP_ROOT):
            continue
        tail = name[len(APP_ROOT):]
        if "/" in tail or not tail.lower().endswith((".dll", ".exe")):
            continue
        key = tail.upper()
        if key in result:
            raise ValueError("Case-insensitive PE filename collision")
        result[key] = row
    if "ADBCD.EXE" not in result:
        raise ValueError("Original executable absent from manifest")
    return result

def _verified_pe(row: dict, parts_dir: Path, known_names: tuple[str, ...]) -> tuple[str, dict | None]:
    """Read one manifest ZIP member, bounded and hash-verified, without extraction."""
    chunks = row["chunks"]
    if len(chunks) != 1:
        return "multi_chunk_not_inspected", None
    chunk = chunks[0]
    if chunk["bytes"] > MAX_PE_BYTES:
        return "oversize_not_inspected", None
    zip_path = parts_dir / chunk["package"]
    if not zip_path.is_file() or zip_path.is_symlink():
        return "package_unavailable", None
    try:
        with zipfile.ZipFile(zip_path) as archive:
            info = archive.getinfo(chunk["entry"])
            if info.file_size != chunk["bytes"]:
                return "size_mismatch", None
            if sum(x.filename == chunk["entry"] for x in archive.infolist()) != 1:
                return "duplicate_zip_member", None
            digest = hashlib.sha256()
            content = bytearray()
            with archive.open(info) as stream:
                while True:
                    part = stream.read(READ_CHUNK)
                    if not part:
                        break
                    if len(content) + len(part) > chunk["bytes"]:
                        return "decompression_exceeds_manifest", None
                    digest.update(part)
                    content.extend(part)
            if len(content) != chunk["bytes"] or digest.hexdigest() != chunk["sha256"].lower():
                return "sha256_mismatch", None
            pe = inspect_pe(bytes(content))
            lowered = bytes(content).lower()
            pe["shipped_dll_name_literals"] = sorted(
                name for name in known_names if name.endswith(".DLL")
                and (name.lower().encode("ascii") in lowered
                     or name.lower().encode("utf-16le") in lowered))
            return "verified", pe
    except (OSError, zipfile.BadZipFile, RuntimeError, KeyError, ValueError, UnicodeError) as exc:
        return "inspection_failed:" + type(exc).__name__, None

def audit(manifest_path: Path, parts_dir: Path) -> dict:
    manifest, _ = load_manifest(manifest_path)
    parts_dir = Path(parts_dir).resolve(strict=True)
    if not parts_dir.is_dir():
        raise ValueError("Parts directory is required")
    targets = _root_pe_files(manifest)
    components = {}
    for name, row in sorted(targets.items()):
        status, pe = _verified_pe(row, parts_dir, tuple(targets))
        components[name] = {"status": status, "bytes": row["size_bytes"]}
        if pe:
            components[name]["pe_format"] = pe["format"]
            components[name]["machine"] = pe["machine"]
            components[name]["direct_imports"] = pe["imported_dlls"]
            components[name]["sentinel_dll_literal_present"] = pe["sentinel_dll_literal_present"]
            components[name]["shipped_dll_name_literals"] = pe["shipped_dll_name_literals"]
    root = components["ADBCD.EXE"]
    if root["status"] != "verified":
        raise ValueError("Main executable not independently verified and parsed")
    if root["machine"] != "0x014c" or root["pe_format"] != "PE32":
        raise ValueError("Unexpected main executable architecture")

    # Only follow direct imports of verified components. Shipped != loaded.
    queue = ["ADBCD.EXE"]
    visited = set()
    reachable = []
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for imported in components[current].get("direct_imports", []):
            key = imported.upper()
            if key in WINDOWS_DLLS:
                classification = "windows_system_candidate"
            elif key in components:
                other = components[key]
                if other["status"] != "verified":
                    classification = "packaged_but_unavailable_or_unverified"
                elif other["machine"] != root["machine"]:
                    classification = "packaged_architecture_mismatch"
                else:
                    classification = "packaged_verified_matching_architecture"
                    queue.append(key)
            else:
                classification = "external_not_in_manifest"
            reachable.append({"importer": current, "dll": imported,
                              "classification": classification})
    sentinel = components.get("SENTINELKEYW.DLL")
    return {
        "schema": "atelierdata-original-runtime-dependency-audit-v1",
        "source": "user_provided_sha256_manifest_and_zip_parts",
        "target_executed": False, "license_checked": False,
        "windows_runtime_tested": False,
        "root_executable": "ADBCD.exe",
        "root_executable_sha256": targets["ADBCD.EXE"]["chunks"][0]["sha256"].lower(),
        "root_architecture": root["machine"],
        "component_count": len(components),
        "verified_component_count": sum(x["status"] == "verified" for x in components.values()),
        "unavailable_component_count": sum(x["status"] == "package_unavailable" for x in components.values()),
        "components": components,
        "reachable_direct_imports": reachable,
        "unresolved_direct_imports": [x for x in reachable if x["classification"] not in
                                      ("windows_system_candidate", "packaged_verified_matching_architecture")],
        "sentinel_literal_candidate": bool(root.get("sentinel_dll_literal_present")),
        "root_shipped_dll_name_literals": root.get("shipped_dll_name_literals", []),
        "sentinel_in_manifest": sentinel is not None,
        "sentinel_available_and_verified": bool(sentinel and sentinel["status"] == "verified"),
        "conclusion": "Static import closure excludes dynamically loaded DLLs. "
                      "Sentinel DLL literal is not proof of mandatory loading. "
                      "Authenticity, license and actual Windows compatibility remain unverified.",
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--parts-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest, args.parts_dir)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(data)
    invalid = [x for x in result["components"].values() if x["status"] not in
               ("verified", "package_unavailable")]
    return 2 if invalid else 0

if __name__ == "__main__":
    raise SystemExit(main())
