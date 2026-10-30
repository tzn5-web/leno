#!/usr/bin/env python3
"""Human authorization gate for private installer builds. Does NOT validate a license."""
import argparse, json, re, sys
from pathlib import Path

ORIGINAL_RAR_SHA256 = "e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da"
ORIGINAL_APP_SHA256 = "a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4"
BUILD_REVIEWS = (
    "source_authenticity_reviewed",
    "vendor_license_evidence_reviewed",
    "installation_instructions_reviewed",
    "sentinel_dependencies_reviewed",
    "version_discrepancy_reviewed",
    "private_distribution_only",
)
RELEASE_REVIEWS = ("isolated_windows_install_pass", "isolated_windows_launch_pass",
                   "isolated_windows_uninstall_pass", "release_binary_signed")

def validate(record: dict, stage: str) -> None:
    if not isinstance(record, dict):
        raise ValueError("REVIEW_RECORD_INVALID")
    if record.get("original_rar_sha256", "").lower() != ORIGINAL_RAR_SHA256:
        raise ValueError("REVIEW_RAR_IDENTITY_MISMATCH")
    if record.get("application_sha256", "").lower() != ORIGINAL_APP_SHA256:
        raise ValueError("REVIEW_APPLICATION_IDENTITY_MISMATCH")
    for field in BUILD_REVIEWS + (RELEASE_REVIEWS if stage == "release" else ()):
        if record.get(field) is not True:
            raise ValueError("REVIEW_REQUIRED:" + field)
    if not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip():
        raise ValueError("REVIEWER_MISSING")
    if not isinstance(record.get("reviewed_at_utc"), str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["reviewed_at_utc"]
    ):
        raise ValueError("REVIEW_TIMESTAMP_MISSING")
    if record.get("license_material_in_public_repo") is not False:
        raise ValueError("PRIVATE_LICENSE_MATERIAL_POLICY_UNCONFIRMED")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--stage", choices=("build", "release"), default="build")
    args = parser.parse_args()
    validate(json.loads(args.record.read_text(encoding="utf-8-sig")), args.stage)
    print(f"PRIVATE_REVIEW_ATTESTATION=PASS stage={args.stage}")
    print("NOTE=Self-declared review, not independent proof of vendor licensing or runtime compatibility.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"PRIVATE_REVIEW_ATTESTATION=FAIL {exc}", file=sys.stderr)
        sys.exit(2)
