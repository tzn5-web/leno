#!/usr/bin/env bash
# Verify ONE real signed K2401 release APK supports both Android install flows.
# Disposable GitHub Android 10 emulator ONLY; never run on the car/head unit.
set -euo pipefail
PKG="ro.evolauncher.k2401"
OLD="${K2401_OLD_SIGNED_APK:-/tmp/k2401-universal-baseline/K2401-EVO-Android10-SIGNED.apk}"
NEW="${K2401_NEW_SIGNED_APK:-K2401-EVO-UPDATE-SIGNED.apk}"
PREF="/data/user/0/$PKG/shared_prefs/universal_install_probe.xml"
CHECK="<string name=\"persisted_state\">KEEP_USER_DATA_ON_UPDATE</string>"
AAPT="$ANDROID_HOME/build-tools/35.0.0/aapt"
test -s "$OLD" && test -s "$NEW" && test -x "$AAPT"
# Explicitly reject physical devices and ordinary user phones.
test "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" = "1" || {
  echo "::error::Universal install verification may run on a disposable emulator only"
  exit 17
}
"$AAPT" dump badging "$OLD" | grep -F "package: name='$PKG'" >/dev/null
"$AAPT" dump badging "$NEW" | grep -F "package: name='$PKG'" >/dev/null
"$AAPT" dump badging "$OLD" | grep -F "versionCode='123'" >/dev/null
"$AAPT" dump badging "$NEW" | grep -F "versionCode='124'" >/dev/null
adb root >/dev/null
adb wait-for-device
test "$(adb shell id -u | tr -d '\r')" = "0"
# Scenario A: device already has previous official v118 -> install v119 over it.
adb shell pm uninstall "$PKG" >/dev/null 2>&1 || true
adb install "$OLD"
adb shell pm path "$PKG" | grep '^package:' >/dev/null
adb shell am start -W -n "$PKG/ro.evolauncher.k2401.MainActivity" >/dev/null
adb shell am force-stop "$PKG"
uid="$(adb shell stat -c %u "/data/user/0/$PKG" | tr -d '\r')"
[[ "$uid" =~ ^[0-9]+$ ]]
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
printf '<map>%s</map>\n' "$CHECK" > "$tmp"
adb push "$tmp" /data/local/tmp/k2401-install-probe.xml >/dev/null
adb shell mkdir -p "/data/user/0/$PKG/shared_prefs"
adb shell cp /data/local/tmp/k2401-install-probe.xml "$PREF"
adb shell chown "$uid:$uid" "$PREF"
adb shell chmod 600 "$PREF"
adb shell restorecon "$PREF"
adb shell rm /data/local/tmp/k2401-install-probe.xml
adb shell cat "$PREF" | grep -F "KEEP_USER_DATA_ON_UPDATE" >/dev/null
adb install -r "$NEW"
adb shell pm path "$PKG" | grep '^package:' >/dev/null
adb shell dumpsys package "$PKG" | grep -F 'versionCode=124' >/dev/null
adb shell cat "$PREF" | grep -F "KEEP_USER_DATA_ON_UPDATE" >/dev/null || {
  echo "::error::User data was lost during same-package signed update"
  exit 18
}
adb shell am start -W -n "$PKG/ro.evolauncher.k2401.MainActivity" >/dev/null
adb shell pidof "$PKG" >/dev/null
echo "K2401_UNIVERSAL_UPDATE_PREVIOUS_SIGNED_V118_TO_V119=PASS"
echo "K2401_UNIVERSAL_UPDATE_PRESERVES_EXISTING_USER_DATA=PASS"
# Scenario B: user uninstalled the launcher -> install SAME APK from zero.
adb shell pm uninstall "$PKG" >/dev/null
adb install "$NEW"
adb shell pm path "$PKG" | grep '^package:' >/dev/null
if adb shell test -f "$PREF"; then
  echo "::error::Uninstalled app's old private preferences unexpectedly persisted"
  exit 19
fi
adb shell am start -W -n "$PKG/ro.evolauncher.k2401.MainActivity" >/dev/null
adb shell pidof "$PKG" >/dev/null
echo "K2401_UNIVERSAL_FRESH_INSTALL_AFTER_UNINSTALL=PASS"
echo "K2401_UNIVERSAL_ONE_APK_BOTH_FLOWS=PASS"
