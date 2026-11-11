#!/usr/bin/env python3
"""Upgrade a previously working Glass+Emoji LatinIME APK without changing keys.
Use the new CI-built classes.dex from the S24-LatinIME-Glass-Emoji-DEX artifact.
The output is unsigned; sign with the SAME developer certificate as installed.
"""
import argparse
import copy
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from patch_picker_gear import update_ime_settings, hide_icon, pool

def run(old_apk: Path, addon_zip: Path, unsigned_apk: Path):
    with ZipFile(addon_zip) as addon:
        addon_dex = addon.read("classes.dex")
    assert addon_dex.startswith(b"dex\n")
    with ZipFile(old_apk) as original, ZipFile(unsigned_apk, "w") as out:
        assert "classes2.dex" in original.namelist(), "Expected previous working Glass build"
        old_xml = original.read("res/xml/method.xml")
        method = update_ime_settings(old_xml)
        manifest = hide_icon(original.read("AndroidManifest.xml"))
        for item in original.infolist():
            name = item.filename
            if name.startswith("META-INF/") and name.upper().endswith((".RSA", ".DSA", ".EC", ".SF", ".MF")):
                continue
            data = (method if name == "res/xml/method.xml"
                    else manifest if name == "AndroidManifest.xml"
                    else addon_dex if name == "classes2.dex"
                    else original.read(name))
            out.writestr(copy.copy(item), data)
    with ZipFile(old_apk) as old, ZipFile(unsigned_apk) as new:
        for name in old.namelist():
            if name not in ("AndroidManifest.xml", "res/xml/method.xml", "classes2.dex"):
                assert old.read(name) == new.read(name), "Original asset changed: " + name
        assert new.read("classes.dex") == old.read("classes.dex")
        assert new.read("classes2.dex") == addon_dex
        assert "com.android.inputmethod.latin.setup.GlassActivity" in pool(new.read("res/xml/method.xml"))[0]
    print("PASS: original keyboard assets unchanged, Glass settings via Android IME gear.")
    print("UNSIGNED output:",unsigned_apk)
    print("Must sign with same key as previously installed test APK.")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("previous_glass_apk",type=Path)
    p.add_argument("addon_artifact_zip",type=Path)
    p.add_argument("output_unsigned_apk",type=Path)
    args=p.parse_args()
    run(args.previous_glass_apk,args.addon_artifact_zip,args.output_unsigned_apk)
