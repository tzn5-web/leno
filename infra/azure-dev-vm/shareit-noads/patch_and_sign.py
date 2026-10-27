#!/usr/bin/env python3
"""Personal-use SHAREit 6.27.58 split-APK ad-endpoint patcher.

Preserves all six original modules. Does not attempt an invalid split->standalone merge.
Requires Android SDK Build Tools 36.0.0 and Java keytool on the Azure development VM.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
import zlib

EXPECTED_SOURCE_SHA256 = "8dcbebc90086c6b1479364066b77bd62f7d2a768cc908799932ed2bdcb6a85fe"
APK_FILES = (
    "base.apk",
    "split_InnoPlayerDynamicFeature.apk",
    "split_InnoPlayerDynamicFeature.config.arm64_v8a.apk",
    "split_ModuleEntertainment.apk",
    "split_ModuleOnline.apk",
    "split_config.arm64_v8a.apk",
)
# Exact advertisement host strings found in user's original DEX files.
AD_HOSTS = (
    "2118c602-ads-access-f681-1832569655.ap-southeast-1.elb.amazonaws.com",
    "api-test.hellay.net", "api.rqmob.com", "cfg.dalyfeds.com",
    "midas-api-stress.hellay.net", "plutus-pre.lacunads.com",
    "plutus-test.lacunads.com", "test.midas-access.ads.sg3.api",
    "plutus.lacunads.com", "app.adjust.cn", "app.adjust.com",
    "app.adjust.net.in", "app.adjust.world", "app.eu.adjust.com",
    "app.tr.adjust.com", "app.us.adjust.com", "pagead2.googlesyndication.com",
    "plutus-track-pre.lacunads.com", "plutus-track-test.lacunads.com",
    "plutus-track.lacunads.com", "www.googleadservices.com",
    "ap-adcs-test.rqmob.com", "ap-adcs.rqmob.com",
    "distribution-test.rqmob.com", "distribution.rqmob.com",
    "test.midas-mediation.ads.sg3.api", "adcs.rqmob.com",
    "appclick.rqmob.com", "midas-api-test.hellay.net",
    "adconf.rqmob.com", "midas-api.hellay.net", "static.rqmob.com",
)
SDK = Path(os.getenv("ANDROID_HOME", "/opt/android-sdk"))
BUILD_TOOLS = SDK / "build-tools" / "36.0.0"
APKSIGNER = str(BUILD_TOOLS / "apksigner")
ZIPALIGN = str(BUILD_TOOLS / "zipalign")
KEYSTORE = Path("/var/lib/shareit-noads/signing.jks")
REPORT = {}

def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def patched_dex(data, counts):
    if not data.startswith(b"dex\\n"):
        return data
    result = data
    # Longer hosts first to avoid consuming substrings of another host.
    for domain in sorted(AD_HOSTS, key=len, reverse=True):
        src = domain.encode("ascii")
        replacement = b"x" * (len(src) - len(b".invalid")) + b".invalid"
        hits = result.count(src)
        if hits:
            result = result.replace(src, replacement)
            counts[domain] = counts.get(domain, 0) + hits
    if result != data:
        mutable = bytearray(result)
        mutable[12:32] = hashlib.sha1(mutable[32:]).digest()
        mutable[8:12] = (zlib.adler32(mutable[12:]) & 0xffffffff).to_bytes(4, "little")
        result = bytes(mutable)
    return result

def prepare_key():
    KEYSTORE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not KEYSTORE.exists():
        import secrets
        passwd = secrets.token_urlsafe(28)
        (KEYSTORE.parent / "keystore_password").write_text(passwd)
        os.chmod(KEYSTORE.parent / "keystore_password", 0o600)
        run("keytool", "-genkeypair", "-keystore", str(KEYSTORE),
            "-alias", "shareit-private", "-keyalg", "RSA", "-keysize", "3072",
            "-validity", "3650", "-dname", "CN=Private Android Testing,O=Personal",
            "-storepass", passwd, "-keypass", passwd, "-noprompt")
        os.chmod(KEYSTORE, 0o600)
    return (KEYSTORE.parent / "keystore_password").read_text().strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("destination")
    p.add_argument("--report", required=True)
    args = p.parse_args()
    raw = Path(args.source).read_bytes()
    if sha256(raw) != EXPECTED_SOURCE_SHA256:
        raise SystemExit("SOURCE_SHA256_MISMATCH: refusing unverified APK version/variant")
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise SystemExit("SOURCE_NOT_APKS")
    counts = {}
    passwd = prepare_key()
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(io.BytesIO(raw)) as source:
        entries = sorted(source.namelist())
        if entries != sorted(APK_FILES):
            raise SystemExit("SOURCE_SPLIT_SET_MISMATCH")
        outputs = {}
        for filename in APK_FILES:
            original = source.read(filename)
            source_apk = Path(td, "original.apk")
            source_apk.write_bytes(original)
            run(APKSIGNER, "verify", str(source_apk))
            modified = Path(td, "unsigned.apk")
            with zipfile.ZipFile(io.BytesIO(original)) as inp, zipfile.ZipFile(modified, "w") as dst:
                for meta in inp.infolist():
                    name = meta.filename
                    if name.startswith("META-INF/") and name.upper().endswith((".SF", ".RSA", ".DSA", ".EC", ".MF")):
                        continue
                    data = inp.read(name)
                    if name.endswith(".dex"):
                        data = patched_dex(data, counts)
                    dst.writestr(meta, data)
            aligned = Path(td, "aligned.apk")
            signed = Path(td, "signed.apk")
            run(ZIPALIGN, "-f", "4", str(modified), str(aligned))
            run(APKSIGNER, "sign", "--ks", str(KEYSTORE), "--ks-key-alias", "shareit-private",
                "--ks-pass", "pass:" + passwd, "--key-pass", "pass:" + passwd,
                "--v2-signing-enabled", "true", "--v3-signing-enabled", "true",
                "--out", str(signed), str(aligned))
            run(APKSIGNER, "verify", "--verbose", str(signed))
            outputs[filename] = signed.read_bytes()
            REPORT[filename] = {"bytes": len(outputs[filename]), "sha256": sha256(outputs[filename])}
        if not counts:
            raise SystemExit("NO_AD_REFERENCES_PATCHED")
        out_path = Path(args.destination)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as out:
            for name in APK_FILES:
                out.writestr(name, outputs[name])
    report = {
        "input_sha256": sha256(raw),
        "output_sha256": sha256(Path(args.destination).read_bytes()),
        "version": "6.27.58_ww", "package": "com.lenovo.anyshare.gps",
        "dex_host_replacements": counts, "files": REPORT,
        "installable_as_one_apk": False,
        "limitations": "Static ad endpoint patch, dynamic ad delivery may remain; no device runtime test.",
        "signature": "New private signing key, all splits signed with same certificate.",
    }
    Path(args.report).write_text(json.dumps(report, indent=2))
    print("SHAREIT_AZURE_STATIC_PATCH_PASS")
    print("DEX_AD_HOST_OCCURRENCES", sum(counts.values()))
    print("OUTPUT_SHA256", report["output_sha256"])

if __name__ == "__main__":
    main()
