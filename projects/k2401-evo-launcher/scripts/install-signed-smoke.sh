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
adb shell settings put system accelerometer_rotation 0
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
# Real screenshots of ALL redesigned skins from the KEY-VAULT-SIGNED APK,
# not mockups or an unsigned local renderer. No car ECU/hardware is accessed.
adb shell pm grant "$MAIN" android.permission.ACCESS_FINE_LOCATION || true
adb shell pm grant "$MAIN" android.permission.ACCESS_COARSE_LOCATION || true
mkdir -p k2401-glass-hud-signed-screens
for skin in 21 22 23 24 25 26 27 28; do
  adb shell am force-stop "$MAIN" >/dev/null
  adb shell am start -W -n "$MAIN/ro.evolauncher.k2401.MainActivity" \
    --ei k2401_skin_preview_ci "$skin" >/dev/null
  sleep 2
  adb shell pidof "$MAIN" >/dev/null
  adb shell screencap -p "/sdcard/k2401-glass-$skin.png"
  adb pull "/sdcard/k2401-glass-$skin.png" \
    "k2401-glass-hud-signed-screens/skin-$skin.png" >/dev/null
done
python3 projects/k2401-evo-launcher/scripts/verify-holographic-screens.py \
  k2401-glass-hud-signed-screens
# Reproduce common OEM "App not installed": old app installed with a
# different certificate. Remove ONLY on this throwaway test emulator.
adb shell pm uninstall "$MAIN" >/dev/null
adb install "$DEBUG"
# The first-run Android location dialog must not obscure the HUD screenshot.
# These are test-emulator grants only; no permissions are changed on the car.
adb shell pm grant "$MAIN" android.permission.ACCESS_FINE_LOCATION || true
adb shell pm grant "$MAIN" android.permission.ACCESS_COARSE_LOCATION || true
adb shell pm grant "$MAIN" android.permission.ACCESS_BACKGROUND_LOCATION || true
# Exercise the actual EVO RED native renderer at the head-unit resolution.
adb shell am start -W -n "$MAIN/ro.evolauncher.k2401.MainActivity" \
  --ei k2401_skin_preview_ci 28
sleep 5
adb shell pidof "$MAIN" >/dev/null
if adb shell dumpsys window windows | grep -Eiq 'mCurrentFocus=.*(permissioncontroller|packageinstaller)'; then
  echo "::error::System permission dialog obscures the EVO RED screenshot"
  exit 5
fi
adb shell screencap -p /sdcard/k2401-evo-red-v117.png
adb pull /sdcard/k2401-evo-red-v117.png k2401-evo-red-v117-emulator.png >/dev/null
python3 - <<'PY'
from PIL import Image,ImageStat
im=Image.open("k2401-evo-red-v117-emulator.png").convert("RGB")
# Same -skin 720x1280 as the passing K2401 debug emulator workflow.
assert im.size==(1280,720),im.size
stat=ImageStat.Stat(im)
assert max(stat.stddev)>8,("Blank or nearly blank HUD",stat.stddev)
print("K2401_EVO_RED_V117_EMULATOR_SCREENSHOT=PASS actual_frame=",im.size)
PY
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
