#!/usr/bin/env bash
set -u
D=/tmp/shareit-ads-visual
mkdir -p "$D"
APP=/tmp/shareit-emu/merged.apk
PKG=com.lenovo.anyshare.gps
adb install -r "$APP" >"$D/install.txt" 2>&1
echo INSTALL_RC=$?
adb shell pm grant "$PKG" android.permission.READ_EXTERNAL_STORAGE 2>/dev/null || true
adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >"$D/launch.txt" 2>&1
sleep 8
# Do not send BACK: it exits SHAREit and yields a misleading Android launcher screenshot.
adb shell am start -n com.lenovo.anyshare.gps/com.lenovo.anyshare.ChangeLogoActivity2 >/dev/null 2>&1 || true
sleep 12
adb shell pidof "$PKG" >"$D/pid.txt" || true
# This is a disposable emulator, not the user's account. Accept onboarding to reach real ads.
adb shell input tap 530 2050 || true
sleep 8
# The next dialog is SHAREit's own permission notice; approve in disposable emulator.
adb shell input tap 845 1592 || true
adb shell appops set "$PKG" MANAGE_EXTERNAL_STORAGE allow 2>/dev/null || true
adb shell pm grant "$PKG" android.permission.POST_NOTIFICATIONS 2>/dev/null || true
sleep 10
# Dismiss optional secondary permission sheet if it appears.
adb shell input tap 840 1595 || true
sleep 5
# Android 16 returns to Settings after granting storage; force the activity stack
# back to SHAREit, checking the *actual* foreground package rather than just the PID.
adb shell appops get "$PKG" MANAGE_EXTERNAL_STORAGE >"$D/storage-appops.txt" 2>&1 || true
adb shell input keyevent KEYCODE_BACK || true
sleep 3
for step in 1 2 3 4; do
  adb shell am force-stop com.android.settings || true
  adb shell am start -W -n "$PKG/com.lenovo.anyshare.main.MainActivity" >>"$D/activity-start.txt" 2>&1 || true
  sleep 7
  F="$(adb shell dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity' | head -1 || true)"
  echo "ATTEMPT_$step $F" >>"$D/foreground-attempts.txt"
  if [[ "$F" == *"$PKG/"* ]]; then break; fi
  adb shell am start -W -n "$PKG/com.lenovo.anyshare.ChangeLogoActivity2" >>"$D/activity-start.txt" 2>&1 || true
  sleep 7
  F="$(adb shell dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity' | head -1 || true)"
  echo "ALIAS_$step $F" >>"$D/foreground-attempts.txt"
  if [[ "$F" == *"$PKG/"* ]]; then break; fi
  adb shell input keyevent KEYCODE_BACK || true
done
adb shell dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity' >"$D/foreground-activity.txt" || true
echo "APP_FOREGROUND_INFO=$(cat "$D/foreground-activity.txt")"
if ! grep -q "$PKG/" "$D/foreground-activity.txt"; then
  echo "SHAREIT_REAL_HOME_NOT_REACHED; visual result must not be called ad-free"
  exit 19
fi
adb shell screencap -p /sdcard/shareit-screen.png
adb pull /sdcard/shareit-screen.png "$D/home.png" >/dev/null 2>&1 || true
adb shell uiautomator dump /sdcard/shareit-ui.xml >"$D/uiautomator-result.txt" 2>&1 || true
adb pull /sdcard/shareit-ui.xml "$D/home.xml" >/dev/null 2>&1 || true
adb shell input swipe 500 1600 500 450 600 || true
sleep 4
adb shell screencap -p /sdcard/shareit-screen2.png
adb pull /sdcard/shareit-screen2.png "$D/home-scrolled.png" >/dev/null 2>&1 || true
adb logcat -d -v brief | grep -Ei 'adsdk|midas|sharead|AdLoader|AdxAdSdk|applovin|ironsource|interstitial|nativead|topon|splash' | tail -n 300 >"$D/ad-logcat.txt" || true
echo "ADS_VISUAL_PROBE_HOME_FOREGROUND_PASS"
ls -l "$D"
