#!/usr/bin/env python3
"""Audit the native JNI binary bundled with the user's Xiaomi LatinIME.apk.

The strict gate deliberately fails if native code has filesystem write
capabilities, because source-level no-history patches cannot prove zero
typed-text retention when a separately compiled library can still write.
Read-only dictionary file access can be legitimate, but must be reviewed.

This is a detection tool, not a binary patcher. No content is uploaded.
"""
import argparse
import subprocess
import tempfile
import zipfile
from pathlib import Path

RISKY_WRITE_SYMBOLS = {
    "fwrite", "write", "writev", "pwrite", "pwrite64", "open",
    "open64", "openat", "rename", "renameat", "remove", "unlink",
    "creat", "fdopen", "fopen", "fopen64",
}
RISKY_NETWORK_SYMBOLS = {
    "socket", "connect", "send", "sendto", "sendmsg", "recv", "recvfrom",
    "getaddrinfo", "SSL_write", "curl_easy_perform",
}

def audit(apk: Path, strict: bool) -> int:
    with zipfile.ZipFile(apk) as source:
        candidates = [x for x in source.namelist()
                      if x.endswith("/libjni_latinimegoogle.so")
                      and ("arm64-v8a" in x or "lib64" in x)]
        if not candidates:
            raise RuntimeError("ARM64 LatinIME JNI library missing")
        native = source.read(candidates[0])
    if native[:4] != b"\x7fELF":
        raise RuntimeError("Native library is not ELF")
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"latinime.so"
        p.write_bytes(native)
        symbols=subprocess.run(["readelf", "--wide", "--dyn-syms", str(p)],
                               capture_output=True,text=True,check=True).stdout
        dynamic=subprocess.run(["readelf", "--dynamic", str(p)],
                               capture_output=True,text=True,check=True).stdout
    undefined=set()
    for line in symbols.splitlines():
        fields=line.split()
        if len(fields)>=8 and fields[6]=="UND":
            undefined.add(fields[7].split("@")[0])
    file_writers=sorted(undefined & RISKY_WRITE_SYMBOLS)
    network=sorted(undefined & RISKY_NETWORK_SYMBOLS)
    print("ABI: ARM64; JNI bytes:",len(native))
    print("Native dynamic library dependencies:")
    for line in dynamic.splitlines():
        if "(NEEDED)" in line: print(" ",line.strip())
    print("Potential native disk write functions:", file_writers)
    print("Potential native network functions:", network)
    if network:
        print("FAIL: network-capable native imports detected")
        return 2
    if file_writers:
        print("INCOMPLETE: native file-writing capabilities remain. Removing "
              "app INTERNET permission does NOT prevent local retention.")
        print("To certify zero typed-text retention, audit all native invocation "
              "paths and dynamic dictionary use on a real device.")
        return 3 if strict else 0
    print("No direct dynamic write/network imports found. This is NOT proof "
          "that every indirect code path is safe.")
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("original_apk",type=Path)
    p.add_argument("--strict-zero-retention",action="store_true")
    args=p.parse_args()
    raise SystemExit(audit(args.original_apk,args.strict_zero_retention))
