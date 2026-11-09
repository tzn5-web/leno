#!/usr/bin/env python3
"""Inject GlassIME/GlassActivity and the emoji panel in an original, working
LatinIME S24 APK. Preserves original DEX/classes, UI resources and keycap pixels.

Input should be an APK with a valid manifest, including all original AOSP
LatinIME resources. This script intentionally produces an UNSIGNED APK.
Sign with Android SDK build-tools apksigner or the user's EXISTING key.
No changes to AOSP dictionary, learning or persistence code are claimed.
"""
import argparse
import copy
import zipfile
from pathlib import Path
from add_launcher import patch as add_launcher_category

CLASS_MAP = {
    "com.android.inputmethod.latin.LatinIME":
        "com.android.inputmethod.latin.GlassIME",
    "com.android.inputmethod.latin.setup.SetupActivity":
        "com.android.inputmethod.latin.setup.GlassActivity",
}

def patch_axml(data: bytes) -> bytes:
    updated = data
    for old, new in CLASS_MAP.items():
        assert len(old) == len(new), (old, new)
        old16, new16 = old.encode("utf-16le"), new.encode("utf-16le")
        n = updated.count(old16)
        if n != 1:
            raise ValueError(f"Expected one UTF16 manifest class {old}, saw {n}")
        updated = updated.replace(old16, new16, 1)
    return updated

def main(source: Path, addon: Path, output: Path):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(addon) as dexzip:
        # The GitHub addon artifact ZIP contains its own classes.dex.
        newdex = dexzip.read("classes.dex") if "classes.dex" in dexzip.namelist() else dexzip.read("glass_addon.dex")
        assert newdex[:4] == b"dex\n"
        names = src.namelist()
        assert "classes.dex" in names
        if "classes2.dex" in names:
            raise ValueError("Source already contains classes2.dex; use a clean original APK")
        manifest = add_launcher_category(patch_axml(src.read("AndroidManifest.xml")))
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", allowZip64=True) as dst:
            for old in src.infolist():
                name = old.filename
                if name.startswith("META-INF/") and name.upper().endswith((".RSA",".SF",".MF",".DSA",".EC")):
                    continue
                data = manifest if name == "AndroidManifest.xml" else src.read(name)
                dst.writestr(copy.copy(old), data)
            dst.writestr("classes2.dex", newdex, compress_type=zipfile.ZIP_DEFLATED)

    with zipfile.ZipFile(source) as a, zipfile.ZipFile(output) as b:
        assert a.read("classes.dex") == b.read("classes.dex")
        assert all(a.read(n) == b.read(n)
                   for n in a.namelist()
                   if n.startswith("res/") or n.startswith("assets/") or n.startswith("lib/"))
        assert all(new.encode("utf-16le") in b.read("AndroidManifest.xml") for new in CLASS_MAP.values())
        assert "android.intent.category.LAUNCHER".encode("utf-16le") in b.read("AndroidManifest.xml")
    print("PASS: original classes.dex, resources, original keys and letters preserved")
    print("Addon: translucent background slider (0-100%), optional blur, emoji browser")
    print("Caution: learning/persistence code in original classes.dex remains unchanged")
    print("Unsigned output:", output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original_apk", type=Path)
    parser.add_argument("addon_zip", type=Path)
    parser.add_argument("unsigned_output", type=Path)
    args = parser.parse_args()
    main(args.original_apk, args.addon_zip, args.unsigned_output)
