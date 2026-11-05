#!/usr/bin/env python3
"""Read-only source preflight for Samsung GT-P5100; not a ROM build gate."""
import json
import pathlib
import re
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent

def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve()
    lock = json.loads((BASE / "sources.lock.json").read_text(encoding="utf-8"))
    errors, checks = [], []
    for src in lock["repositories"]:
        folder = root / src["path"]
        if not folder.is_dir():
            errors.append(f"MISSING_SOURCE:{src['path']}")
            continue
        try:
            head = subprocess.check_output(["git", "-C", str(folder), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
            if head != src["revision"]:
                errors.append(f"WRONG_REVISION:{src['path']}:{head}")
            else:
                checks.append(f"PINNED:{src['path']}")
        except (OSError, subprocess.CalledProcessError):
            errors.append(f"NOT_GIT:{src['path']}")
    def read(rel):
        path = root / rel
        if not path.is_file():
            errors.append(f"MISSING_FILE:{rel}")
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    if not errors:
        board = read("device/samsung/espresso3g/BoardConfig.mk")
        common = read("device/samsung/espressowifi/BoardConfigCommon.mk")
        device = read("device/samsung/espresso3g/device.mk")
        if not re.search(r"TARGET_OTA_ASSERT_DEVICE\s*:=.*(?:GT-P5100|p5100)", board):
            errors.append("NO_P5100_ASSERT")
        if "GT-P5110" in board or "p5110" in board:
            errors.append("WIFI_ONLY_MODEL_IN_3G_ASSERT")
        if not re.search(r"TARGET_KERNEL_SOURCE\s*:=\s*kernel/ti/omap4", common):
            errors.append("KERNEL_SOURCE_MISMATCH")
        if not re.search(r"BOARD_SYSTEMIMAGE_PARTITION_SIZE\s*:=\s*1073741824", common):
            errors.append("LEGACY_SYSTEM_PARTITION_SIZE_MISMATCH")
        if not re.search(r"BOARD_BOOTIMAGE_PARTITION_SIZE\s*:=\s*8388608", common):
            errors.append("LEGACY_BOOT_PARTITION_SIZE_MISMATCH")
        if "libsecril-client" not in device or "android.hardware.telephony.gsm.xml" not in device:
            errors.append("MISSING_3G_DEVICE_CONFIG")
        if not errors:
            checks.append("LEGACY_DEVICE_TREE_CONSISTENCY=PASS")
    report = {"model":"GT-P5100","stage":"LEGACY_SOURCE_PREFLIGHT",
              "result":"PASS" if not errors else "BLOCKED",
              "checks":checks,"errors":errors,"flash_allowed":False,
              "android14_bootable":False,"note":"PASS only validates pinned legacy sources; it never validates a ROM or device."}
    print(json.dumps(report, indent=2))
    print("NO_FLASH=YES")
    return 0 if not errors else 2

if __name__ == "__main__":
    sys.exit(main())
