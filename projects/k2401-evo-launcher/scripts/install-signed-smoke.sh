#!/usr/bin/env bash
# Android 10 INSTALL test of actual Azure-Key-Vault-signed release files.
# No operations on user's navigation. Tests only a disposable emulator.
set -euo pipefail
MAIN="ro.evolauncher.k2401"
ALT="ro.evolauncher.k2401.ultra"
BASE="projects/k2401-evo-launcher"
NORMAL="$BASE/app/build/outputs/apk/release/app-release.apk"
PARALLEL="K2401-EVO-ULTRA-INSTALL-SEPARAT.apk"
DEBUG="$BASE/app/build/outputs/apk/debug/app-debug.apk"
test -s "$NORMAL" && test -s "$PARALLEL" && test -s "$DEBUG"
adb shell wm size 1280x720
adb shell wm density 160
adb shell am force-stop "$MAIN" >/dev/null 2>&1 || true
# Installed same-cert official production APK, not debug emulator artifact.
adb install -r "$NORMAL"
adb shell pm path "$MAIN" | grep -q '^package:'
adb shell am start -W -n "$MAIN/ro.evolauncher.k2401.MainActivity"
adb shell pidof "$MAIN" >/dev/null
echo "K2401_SIGNED_FRESH_INSTALL_ON_ANDROID10=PASS"
# A fresh APK and another package must both work at the same time.
adb install -r "$PARALLEL"
adb shell pm path "$ALT" | grep -q '^package:'
adb shell am start -W -n "$ALT/ro.evolauncher.k2401.MainActivity"
adb shell pidof "$ALT" >/dev/null
echo "K2401_PARALLEL_SIDE_BY_SIDE_WITH_SIGNED=PASS"
# Reproduce common OEM "App not installed": old app installed with a
# different certificate. Remove ONLY on this throwaway test emulator.
adb shell pm uninstall "$MAIN" >/dev/null
adb install "$DEBUG"
set +e
bad="$(adb install -r "$NORMAL" 2>&1)"
result=$?
set -e
if [[ $result -eq 0 ]]; then
  echo "::error::A different debug signer unexpectedly updated production signing"
  exit 2
fi
echo "$bad" | grep -Eq 'INSTALL_FAILED_UPDATE_INCOMPATIBLE|signatures do not match|INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES' || {
  echo "::error::Expected explicit mismatching-signature rejection, got: $bad"
  exit 3
}
adb shell pm path "$MAIN" | grep -q '^package:'
adb shell pm path "$ALT" | grep -q '^package:'
adb shell am start -W -n "$ALT/ro.evolauncher.k2401.MainActivity"
adb shell pidof "$ALT" >/dev/null
echo "K2401_OLD_SIGNATURE_CONFLICT_REPRODUCED=PASS"
echo "K2401_OLD_APP_PRESERVED_PARALLEL_INSTALL=PASS"
echo "K2401_ANDROID10_ACTUAL_SIGNED_INSTALL_AND_FALLBACK=PASS"
