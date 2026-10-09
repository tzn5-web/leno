#!/usr/bin/env python3
"""Defensive, read-only security triage for the untrusted IPA candidate.

No result can prove a proprietary binary contains no malicious code.
"""
import argparse
import hashlib
import importlib.util
import json
import plistlib
import re
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_audit", HERE / "verify_source.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

PINNED_CANDIDATE_SHA256 = "6cfef4ca82720f385b4ab3a7e7171cefb2d95d552d88f15cabe1b559bcf80154"
SUSPICIOUS_PATTERNS = {
    "webhook_exfiltration": re.compile(rb"(?i)https?://(?:[\w.-]*\.)?(?:webhook\.site|requestbin\.net|pipedream\.net|ngrok-free\.app|ngrok\.io)(?:/|\\b)"),
    "messaging_bots": re.compile(rb"(?i)https?://(?:api\.telegram\.org/bot|discord\.com/api/webhooks/|discordapp\.com/api/webhooks/)"),
    "shell_download_execute": re.compile(rb"(?i)(?:curl|wget)\s+[^\r\n]{1,250}\s*\|\s*(?:sh|bash)\b"),
}
EXEC_HINTS = (".dylib", ".so", ".sh", ".py", ".js", ".appex", ".framework/")
MAX_SAMPLE = 200*1024*1024

def scan(path):
    result = audit_module.audit(path)
    evidence = {
        "sha256": result["sha256"],
        "pinned_candidate_hash_matches": result["sha256"] == PINNED_CANDIDATE_SHA256,
        "static_base_status": result["status"],
        "not_a_malware_free_attestation": True,
        "official_google_binary_match": False,
        "scanned_binary_paths": [],
        "bundled_dynamic_libraries": [],
        "extension_count": 0,
        "suspicious_literal_indicators": [],
        "sensitive_usage_descriptions": {},
        "ats_policy": {},
        "first_party_signature_verified": False,
        "risk_status": "QUARANTINE_UNVERIFIED_ORIGIN"
    }
    with zipfile.ZipFile(path) as archive:
        info = plistlib.loads(archive.read("Payload/YouTube.app/Info.plist"))
        for key in sorted(info):
            if key.endswith("UsageDescription"):
                evidence["sensitive_usage_descriptions"][key] = bool(info[key])
        evidence["ats_policy"] = info.get("NSAppTransportSecurity", {})
        patterns = Counter()
        total_sampled = 0
        names = archive.namelist()
        evidence["extension_count"] = len([name for name in names if name.endswith(".appex/Info.plist")])
        for name in names:
            if name.endswith("/"):
                continue
            if (name.endswith(".dylib") or (".framework/" in name and name.split("/")[-1].split(".")[0] != "Info") or
                name.endswith(".sh") or name.endswith(".py")):
                evidence["bundled_dynamic_libraries"].append(name)
            # Only look at Mach-O code and package scripts for exfiltration IOCs. Do not execute.
            item = archive.getinfo(name)
            if item.file_size > MAX_SAMPLE:
                continue
            check = (name == "Payload/YouTube.app/YouTube" or
                     name.endswith(".dylib") or
                     ".framework/" in name and "/_CodeSignature/" not in name or
                     name.endswith((".sh", ".py")))
            if not check or total_sampled > 800*1024*1024:
                continue
            data = archive.read(name)
            total_sampled += len(data)
            if data[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf"):
                evidence["scanned_binary_paths"].append(name)
            for label, pattern in SUSPICIOUS_PATTERNS.items():
                if pattern.search(data):
                    patterns[(label, name)] += 1
        evidence["suspicious_literal_indicators"] = [
            {"category": label, "path": name, "present": True}
            for (label, name), _ in patterns.most_common(60)
        ]
        evidence["scanned_code_bytes"] = total_sampled
        evidence["bundled_dynamic_libraries"] = sorted(set(evidence["bundled_dynamic_libraries"]))[:400]
        evidence["scanned_binary_paths"] = sorted(evidence["scanned_binary_paths"])[:400]
    return evidence

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ipa", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = scan(args.ipa)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in
          ("sha256", "pinned_candidate_hash_matches", "static_base_status",
           "risk_status", "extension_count", "suspicious_literal_indicators", "scanned_code_bytes")},
          ensure_ascii=False, indent=2))
    if not report["pinned_candidate_hash_matches"]:
        raise SystemExit("Candidate SHA mismatch: quarantined")
    if report["static_base_status"] != "STRUCTURE_PASS_PROVENANCE_UNVERIFIED":
        raise SystemExit("Unexpected binary modifications: quarantined")
