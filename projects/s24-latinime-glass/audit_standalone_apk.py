#!/usr/bin/env python3
"""Strict pre-install audit for the actual ORIGINAL Xiaomi-based Glass APK.

No sample LatinIME fixture is accepted. This is a static gate; it cannot
certify runtime behavior or no native text retention. Does not upload files.
"""
import argparse
import hashlib
import struct
import zipfile
from pathlib import Path

from audit_full_apk import start_elements

PACKAGE = "com.android.inputmethod.latin"
SERVICE = PACKAGE + ".LatinIME"
SETTINGS = PACKAGE + ".setup.GlassActivity"
JNI = "lib/arm64-v8a/libjni_latinimegoogle.so"


def check(path: Path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, "Corrupted APK ZIP"
        contents = set(z.namelist())
        assert {"AndroidManifest.xml", "classes.dex", "classes2.dex",
                "res/xml/method.xml", JNI} <= contents, "Missing core APK entries"
        manifest = list(start_elements(z.read("AndroidManifest.xml")))
        methods = list(start_elements(z.read("res/xml/method.xml")))
        service = [(name, a) for name,a in manifest if name == "service"
                   and a.get("permission") == "android.permission.BIND_INPUT_METHOD"]
        assert len(service) == 1 and service[0][1].get("name") == SERVICE, (
            "Android will not load the original LatinIME component")
        settings = [a for name,a in methods if name == "input-method"]
        assert len(settings) == 1 and settings[0].get("settingsActivity") == SETTINGS, (
            "Settings gear does not open Glass")
        assert any(name == "activity" and a.get("name") == SETTINGS
                   for name,a in manifest), "GlassActivity not declared"
        assert not any(name.startswith("uses-permission") for name,a in manifest), (
            "Privacy gate: manifest declares permissions")
        app = [a for name,a in manifest if name == "application"]
        assert len(app) == 1 and app[0].get("allowBackup") == 0, (
            "Privacy gate: backup not disabled")
        assert all(a.get("name") != "android.intent.category.LAUNCHER"
                   for name,a in manifest if name == "category"), (
            "Unexpected separate launcher icon; settings should be in IME")
        base, addon = z.read("classes.dex"), z.read("classes2.dex")
        assert base.startswith(b"dex\n") and addon.startswith(b"dex\n"), "Invalid DEX"
        assert b"XiaomiIMECore" in base and b"LatinIME" in addon, "Missing class rebind"
        assert b"GlassIME;" not in addon, "Stale service name in addon DEX"
        assert b"GlassActivity" in addon and b"GlassEmojiPanel" in addon, (
            "Glass/emoji classes missing")
        native = z.read(JNI)
        assert native[:4] == b"\x7fELF", "JNI is not an ELF"
        assert native[4] == 2 and native[5] == 1, "JNI ELF must be ELF64 little endian"
        assert struct.unpack_from("<H",native,18)[0] == 183, "JNI must be AArch64"
        assert b"JNI_OnLoad" in native and (
            b"com/android/inputmethod/latin/BinaryDictionary" in native), (
            "JNI registration mismatch")

        # The full keyboard must retain its own dictionary and layout files.
        resources = [n for n in contents if n.startswith(("assets/","res/"))]
        assert len(resources) >= 1000, "Fixture APK, not the full Xiaomi keyboard"
        print("PASS full original Xiaomi APK structure:",len(contents),"entries")
        print("PASS stable IME service and custom settings, no requested permissions")
        print("PASS ARM64 JNI and DEX class rebinding; visual assets retained")
        print("QA SHA256",hashlib.sha256(path.read_bytes()).hexdigest())
        print("RUNTIME LIMIT: AArch64 JNI requires an ARM64 device or compatible emulator bridge")
        print("PRIVACY LIMIT: native dictionary file-write paths not yet excluded")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk",type=Path)
    args = parser.parse_args()
    check(args.apk)
