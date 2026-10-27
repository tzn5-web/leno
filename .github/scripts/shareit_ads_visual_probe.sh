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
adb shell input keyevent KEYCODE_BACK || true
sleep 5
adb shell input tap 500 1700 || true
sleep 4
adb shell screencap -p /sdcard/shareit-screen.png
adb pull /sdcard/shareit-screen.png "$D/home.png" >/dev/null 2>&1 || true
adb shell uiautomator dump /sdcard/shareit-ui.xml >"$D/uiautomator-result.txt" 2>&1 || true
adb pull /sdcard/shareit-ui.xml "$D/home.xml" >/dev/null 2>&1 || true
adb shell input swipe 500 1600 500 450 600 || true
sleep 4
adb shell screencap -p /sdcard/shareit-screen2.png
adb pull /sdcard/shareit-screen2.png "$D/home-scrolled.png" >/dev/null 2>&1 || true
adb logcat -d -v brief | grep -Ei 'adsdk|midas|sharead|AdLoader|AdxAdSdk|applovin|ironsource|interstitial|nativead|topon|splash' | tail -n 300 >"$D/ad-logcat.txt" || true
echo "ADS_VISUAL_PROBE_PASS"
ls -l "$D"
