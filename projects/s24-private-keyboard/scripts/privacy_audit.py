#!/usr/bin/env python3
"""Fail closed if dangerous permissions or data/network APIs enter our source."""
from pathlib import Path
import xml.etree.ElementTree as ET

project = Path(__file__).resolve().parents[1]
manifest = project / "app/src/main/AndroidManifest.xml"
root = ET.parse(manifest).getroot()
android = "{http://schemas.android.com/apk/res/android}"
permissions = [p.attrib.get(android + "name") for p in root.findall("uses-permission")]
assert not permissions, f"Unexpected permission declarations: {permissions}"
app = root.find("application")
assert app is not None and app.attrib.get(android + "allowBackup") == "false"
assert app.attrib.get(android + "usesCleartextTraffic") == "false"
services = app.findall("service")
assert len(services) == 1 and services[0].attrib.get(android+"permission") == "android.permission.BIND_INPUT_METHOD"
sources = "\n".join(p.read_text(encoding="utf-8") for p in project.glob("app/src/main/java/**/*.java"))
for token in (
    "android.util.Log", "java.net.", "android.webkit.",
    "FileOutputStream", "FileWriter", "getClipboard", "HttpURLConnection",
    "Socket(", "DatagramSocket(", "TelephonyManager", "MediaRecorder",
    "Firebase", "Analytics", "SQLite", "RoomDatabase", "getContentResolver(",
):
    assert token not in sources, f"Disallowed API: {token}"
print("PASS: zero app permissions; appearance-only local preferences; no source network/logging APIs.")
