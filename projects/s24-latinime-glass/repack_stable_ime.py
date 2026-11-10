#!/usr/bin/env python3
"""Package the original Xiaomi keyboard with a verified, stable LatinIME service.

Unlike the earlier GlassIME service replacement, Android keeps the exact same
component name (com.android.inputmethod.latin.LatinIME), so the chosen IME in
Settings remains valid across updates. DexServiceRebind must first rewrite:
- old LatinIME -> XiaomiIMECore
- addon GlassIME -> LatinIME (extends XiaomiIMECore)

Only APK UI resources, dictionaries and native libs are kept byte-identical.
Modified DEX and manifest must be signed with Android SDK apksigner.
"""
import argparse
import copy
import zipfile
from pathlib import Path

from patch_picker_gear import pool, update_ime_settings, hide_icon
from audit_full_apk import start_elements

ORIGINAL = "com.android.inputmethod.latin.LatinIME"
GLASS = "com.android.inputmethod.latin.GlassIME"
GEAR = "com.android.inputmethod.latin.setup.GlassActivity"

def manifest_stable(blob):
    names, _, _, _ = pool(blob)
    old = GLASS.encode("utf-16le")
    new = ORIGINAL.encode("utf-16le")
    if GLASS in names:
        if blob.count(old) != 1 or len(old) != len(new):
            raise RuntimeError("Unexpected binary manifest service format")
        blob = blob.replace(old, new, 1)
    elif ORIGINAL not in names:
        raise RuntimeError("No original LatinIME component in manifest")
    if GLASS in pool(blob)[0]:
        raise RuntimeError("Old GlassIME component was not removed")
    # AXML string pools retain unused strings even after a launcher category
    # element is removed. Test actual start elements, not mere string presence.
    # This makes rebuilding from the user's previous GEAR APK idempotent.
    active_launcher = any(
        element == "category" and attributes.get("name") == "android.intent.category.LAUNCHER"
        for element, attributes in start_elements(blob)
    )
    if active_launcher:
        blob = hide_icon(blob)
    assert not any(
        element == "category" and attributes.get("name") == "android.intent.category.LAUNCHER"
        for element, attributes in start_elements(blob)
    ), "Launcher category must remain disabled"
    return blob

def method_with_gear(blob):
    names, _, _, _ = pool(blob)
    if GEAR in names:
        return blob
    return update_ime_settings(blob)

def build(original_apk, base_dex, addon_dex, unsigned_apk):
    dex1 = base_dex.read_bytes()
    dex2 = addon_dex.read_bytes()
    if not dex1.startswith(b"dex\n") or not dex2.startswith(b"dex\n"):
        raise RuntimeError("Output from DexServiceRebind is required")
    with zipfile.ZipFile(original_apk) as source, zipfile.ZipFile(
            unsigned_apk, "w", allowZip64=True) as target:
        metadata = manifest_stable(source.read("AndroidManifest.xml"))
        method = method_with_gear(source.read("res/xml/method.xml"))
        for entry in source.infolist():
            name = entry.filename
            if name.startswith("META-INF/") and name.upper().endswith(
                    (".RSA", ".DSA", ".EC", ".SF", ".MF")):
                continue
            if name == "AndroidManifest.xml":
                payload = metadata
            elif name == "res/xml/method.xml":
                payload = method
            elif name == "classes.dex":
                payload = dex1
            elif name == "classes2.dex":
                payload = dex2
            else:
                payload = source.read(name)
            target.writestr(copy.copy(entry), payload)
        if "classes2.dex" not in source.namelist():
            target.writestr("classes2.dex", dex2, compress_type=zipfile.ZIP_DEFLATED)

    with zipfile.ZipFile(original_apk) as a, zipfile.ZipFile(unsigned_apk) as b:
        for name in a.namelist():
            if name.startswith(("res/", "assets/", "lib/")) and name != "res/xml/method.xml":
                if a.read(name) != b.read(name):
                    raise RuntimeError("Original key layout/resource changed: " + name)
        if ORIGINAL not in pool(b.read("AndroidManifest.xml"))[0]:
            raise RuntimeError("Android will not find original LatinIME service")
        if GEAR not in pool(b.read("res/xml/method.xml"))[0]:
            raise RuntimeError("Android gear does not point to Glass settings")
        if b.read("classes.dex") != dex1 or b.read("classes2.dex") != dex2:
            raise RuntimeError("Changed DEX payloads")
    print("PASS: unchanged original keys/letters, gear metadata, stable LatinIME service")
    print("UNSIGNED:", unsigned_apk)
    print("Runtime and local data persistence still require verification")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("renamed_original_dex", type=Path)
    parser.add_argument("renamed_addon_dex", type=Path)
    parser.add_argument("unsigned_apk", type=Path)
    args = parser.parse_args()
    build(args.old_apk, args.renamed_original_dex,
          args.renamed_addon_dex, args.unsigned_apk)
