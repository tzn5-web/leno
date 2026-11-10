#!/usr/bin/env bash
# Real Xiaomi APK test, not the synthetic LatinIME extension fixture.
# Runs on disposable Android 16 emulator; private APK is never uploaded
# as a public artifact. Fail closed on ABI, package collision or crashes.
set -euo pipefail

OUT="build/full"
mkdir -p "$OUT"
touch "$OUT/test-result.txt"
exec > >(tee -a "$OUT/test-result.txt") 2>&1

# This is a TEST-ONLY alias package: the Java IME class name stays original.
# It coexists with the system LatinIME and avoids overwriting Android's IME.
pkg="com.android.inputmethod.s24qa"
svc="$pkg/com.android.inputmethod.latin.LatinIME"
ap="$OUT/xiaomi-test.apk"
probe="$OUT/probe-test.apk"
[[ -f "$ap" && -f "$probe" ]] || {
  echo "BLOCKED: missing compiled full Xiaomi APK or test editor"; exit 80;
}
echo "Android image: $(adb shell getprop ro.build.version.release)"
echo "Available device ABIs: $(adb shell getprop ro.product.cpu.abilist)"
echo "Native bridge: $(adb shell getprop ro.dalvik.vm.native.bridge)"
echo "Existing package (if system-preinstalled):"
adb shell pm path "$pkg" || true

# AOSP emulators frequently contain a different system-signed AOSP LatinIME
# under the SAME Android package name. Never erase it silently.
installed_before="$(adb shell pm path "$pkg" || true)"
if [[ -n "$installed_before" ]]; then
  echo "BLOCKED: private QA alias $pkg is already installed; refusing overwrite." >&2
  echo "A different signer cannot overwrite an existing QA app. Choose an" >&2
  echo "empty throwaway emulator with a clean QA alias." >&2
  echo "No system keyboard was uninstalled." >&2
  exit 81
fi

# Android 16 x86_64 AOSP images may lack ARM translation. The original
# Xiaomi JNI is AArch64-only, so a generic x86 emulator is not sufficient.
echo "Installing the real signed ARM64-only Xiaomi APK."
if ! adb install -r "$ap" > "$OUT/install-result.txt" 2>&1; then
  cat "$OUT/install-result.txt"
  echo "BLOCKED: installation failed, likely NO_MATCHING_ABIS or package policy." >&2
  exit 82
fi
echo "PASS: full Xiaomi APK actually installed (not merely compiled)."

if ! adb install -r "$probe"; then
  echo "BLOCKED: editable test app could not install" >&2
  exit 83
fi
adb shell settings put secure show_ime_with_hard_keyboard 1
adb shell ime enable "$svc"
adb shell ime set "$svc"
adb shell am start -n dev.tzn5.xiaomitest/.ProbeActivity
sleep 5
adb shell input tap 190 160
sleep 3

adb shell dumpsys input_method > "$OUT/ime-state.txt"
if ! grep -q "mInputShown=true" "$OUT/ime-state.txt"; then
  echo "FAIL: full Xiaomi input method never appeared in Android 16" >&2
  adb shell ime list -a -s || true
  exit 84
fi
adb shell screencap -p /sdcard/full-ime-open.png
adb pull /sdcard/full-ime-open.png "$OUT/ime-open.png" >/dev/null
echo "PASS: full original Xiaomi core loaded under test-only alias and IME window visible."

# The actual GlassActivity must be launchable from the full APK.
adb shell am start -n "$pkg/com.android.inputmethod.latin.setup.GlassActivity"
sleep 2
adb shell uiautomator dump /sdcard/glass-settings.xml >/dev/null
adb pull /sdcard/glass-settings.xml "$OUT/glass-settings.xml" >/dev/null
if ! grep -q "Opacitate" "$OUT/glass-settings.xml"; then
  echo "FAIL: full original Xiaomi APK settings activity did not show Glass slider" >&2
  exit 85
fi
echo "PASS: Glass settings screen opens in the full Xiaomi APK."

adb shell am start -n dev.tzn5.xiaomitest/.ProbeActivity
sleep 2
adb shell input tap 190 160
sleep 2
adb logcat -c
for i in $(seq 1 12); do
  adb shell input keyevent 4
  sleep .3
  adb shell input tap 190 160
  sleep .8
  if ! adb shell dumpsys input_method | grep -q 'mInputShown=true'; then
    echo "FAIL: full Xiaomi keyboard missing on open/close cycle $i" >&2
    exit 86
  fi
done
adb logcat -d -v brief | grep -E 'Process: com.android.inputmethod.s24qa|FATAL EXCEPTION' \
  > "$OUT/fatal-summary.txt" || true
if grep -q "Process: com.android.inputmethod.s24qa" "$OUT/fatal-summary.txt"; then
  echo "FAIL: complete Xiaomi IME crashed on Android 16" >&2
  exit 87
fi
echo "PASS: full original Xiaomi APK survived 12 input-view lifecycle cycles."
echo "LIMITATION: no OEM Samsung One UI or native no-retention certification."
