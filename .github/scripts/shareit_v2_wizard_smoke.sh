#!/usr/bin/env bash
# Executed as ONE shell script by reactivecircus android-emulator-runner script: bash ...
set -u
DIR=/tmp/shareit-emu
PKG=com.lenovo.anyshare.gps
ALIAS=com.lenovo.anyshare.ChangeLogoActivity2
BASELINE_INSTALL=1
SINGLE_INSTALL=1
BASELINE_PID=""
SINGLE_PID=""
DEFAULT_LAUNCH=0
FORCED_ALIAS_LAUNCH=0
{
  echo "EMULATOR_VERSION=$(adb shell getprop ro.build.version.release)"
  echo "EMULATOR_ABIS=$(adb shell getprop ro.product.cpu.abilist)"
  echo "ARM_NATIVE_BRIDGE=$(adb shell getprop ro.dalvik.vm.native.bridge)"
  adb devices -l
} | tee "$DIR/emulator-info.txt"
adb install-multiple "$DIR"/splits/*.apk >"$DIR/baseline-install.log" 2>&1
BASELINE_INSTALL=$?
echo "BASELINE_INSTALL_RC=$BASELINE_INSTALL"
if [ "$BASELINE_INSTALL" -eq 0 ]; then
  adb logcat -c || true
  adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >"$DIR/baseline-launch.log" 2>&1 || true
  sleep 10
  BASELINE_PID="$(adb shell pidof "$PKG" | tr -d '\r' || true)"
  if [[ -z "$BASELINE_PID" ]]; then
    echo 'BASELINE_HAS_NO_ENABLED_LAUNCHER; trying exported original alias'
    adb shell pm enable "$PKG/$ALIAS" >"$DIR/baseline-enable-alias.log" 2>&1 || true
    adb shell am start -n "$PKG/$ALIAS" >"$DIR/baseline-alias-launch.log" 2>&1 || true
    sleep 8
    BASELINE_PID="$(adb shell pidof "$PKG" | tr -d '\r' || true)"
  fi
  adb uninstall "$PKG" >"$DIR/baseline-uninstall.log" 2>&1 || true
fi
echo "BASELINE_APP_PID=${BASELINE_PID:-missing}"
adb logcat -c || true
adb install "$DIR/merged.apk" >"$DIR/single-install.log" 2>&1
SINGLE_INSTALL=$?
echo "SINGLE_INSTALL_RC=$SINGLE_INSTALL"
if [ "$SINGLE_INSTALL" -eq 0 ]; then
  adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >"$DIR/single-launch.log" 2>&1 || true
  sleep 10
  SINGLE_PID="$(adb shell pidof "$PKG" | tr -d '\r' || true)"
  if [[ -n "$SINGLE_PID" ]]; then
    DEFAULT_LAUNCH=1
  else
    echo 'SINGLE_HAS_NO_ENABLED_LAUNCHER; trying original alias'
    adb shell pm enable "$PKG/$ALIAS" >"$DIR/single-enable-alias.log" 2>&1 || true
    adb shell am start -n "$PKG/$ALIAS" >"$DIR/single-alias-launch.log" 2>&1 || true
    sleep 14
    SINGLE_PID="$(adb shell pidof "$PKG" | tr -d '\r' || true)"
    if [[ -n "$SINGLE_PID" ]]; then FORCED_ALIAS_LAUNCH=1; fi
  fi
fi
echo "SINGLE_APP_PID=${SINGLE_PID:-missing}"
adb logcat -d -v threadtime >"$DIR/logcat.log" 2>/dev/null || true
cat "$DIR/baseline-install.log" 2>/dev/null || true
cat "$DIR/single-install.log" 2>/dev/null || true
cat "$DIR/single-launch.log" 2>/dev/null || true
cat "$DIR/single-alias-launch.log" 2>/dev/null || true
echo 'TEST_ONBOARDING_ACCEPTANCE_START'
adb shell input tap 530 2040 || true
sleep 20
adb exec-out screencap -p > "$DIR/shareit-v2-after-consent.png" 2>/dev/null || true
adb shell uiautomator dump /sdcard/shareit-v2-after-consent.xml >/dev/null 2>&1 || true
adb pull /sdcard/shareit-v2-after-consent.xml "$DIR/shareit-v2-after-consent.xml" >/dev/null 2>&1 || true
echo 'TEST_ONBOARDING_ACCEPTANCE_SCREEN_CAPTURED'

echo 'PERMISSIONS_WIZARD_AUTO_NAVIGATION'
for round in 1 2 3 4 5 6; do
  adb shell uiautomator dump /sdcard/shareit-wizard.xml >/dev/null 2>&1 || true
  adb pull /sdcard/shareit-wizard.xml "$DIR/shareit-wizard.xml" >/dev/null 2>&1 || true
  coord="$(python3 - <<'PY'
import xml.etree.ElementTree as ET,re
try: r=ET.parse('/tmp/shareit-emu/shareit-wizard.xml').getroot()
except Exception: raise SystemExit(0)
for n in r.iter('node'):
 a=n.attrib
 t=(a.get('text') or a.get('content-desc') or '').strip().lower()
 # Only follow file access permissions and basic onboarding, never promo content.
 if t in ('allow','while using the app','allow only while using the app','allow access to manage all files','continue','not now','skip','ok','got it','next','allow all'):
  b=re.findall(r'\d+',a.get('bounds',''))
  if len(b)==4:
   x=(int(b[0])+int(b[2]))//2;y=(int(b[1])+int(b[3]))//2
   print(x,y,t.replace(' ','_'));raise SystemExit
PY
)"
  if [ -z "$coord" ]; then
    echo "NO_MORE_PERMISSION_DIALOGS_AFTER_$round"
    break
  fi
  echo "PERMISSION_STEP_$round ${coord##* }"
  adb shell input tap $(echo "$coord" | cut -d' ' -f1-2) || true
  sleep 5
  adb exec-out screencap -p > "$DIR/shareit-v2-round-$round.png" 2>/dev/null || true
done
adb exec-out screencap -p > "$DIR/shareit-v2-final-screen.png" 2>/dev/null || true
adb shell uiautomator dump /sdcard/shareit-v2-final.xml >/dev/null 2>&1 || true
adb pull /sdcard/shareit-v2-final.xml "$DIR/shareit-v2-final.xml" >/dev/null 2>&1 || true

echo "CAPTURE_SINGLE_APP_SCREEN=START"
adb exec-out screencap -p > "$DIR/shareit-v2-screen.png" 2>/dev/null || true
adb shell uiautomator dump /sdcard/shareit-v2-ui.xml >/dev/null 2>&1 || true
adb pull /sdcard/shareit-v2-ui.xml "$DIR/shareit-v2-ui.xml" >/dev/null 2>&1 || true
export SHAREIT_BASELINE_RC="$BASELINE_INSTALL"
export SHAREIT_SINGLE_RC="$SINGLE_INSTALL"
export SHAREIT_BASELINE_PID="$BASELINE_PID"
export SHAREIT_SINGLE_PID="$SINGLE_PID"
export SHAREIT_DEFAULT_LAUNCH="$DEFAULT_LAUNCH"
export SHAREIT_ALIAS_LAUNCH="$FORCED_ALIAS_LAUNCH"
python3 - <<'PY'
import pathlib,json,os,re
d=pathlib.Path('/tmp/shareit-emu')
bl=(d/'baseline-install.log').read_text(errors='replace') if (d/'baseline-install.log').exists() else ''
si=(d/'single-install.log').read_text(errors='replace') if (d/'single-install.log').exists() else ''
log=(d/'logcat.log').read_text(errors='replace') if (d/'logcat.log').exists() else ''
fatal_matches=[]
for m in re.finditer('FATAL EXCEPTION',log):
    segment=log[m.start():m.start()+1600]
    if re.search(r'Process: com\.lenovo\.anyshare\.gps(?:[:,\s]|$)',segment):
        fatal_matches.append(segment[:4500])
baseline_ok = os.environ.get('SHAREIT_BASELINE_RC')=='0'
single_ok = os.environ.get('SHAREIT_SINGLE_RC')=='0'
alive = bool(os.environ.get('SHAREIT_SINGLE_PID','').strip())
obj={
 'emulator':'Android 16 Google APIs x86_64 (ARM64 binary translation via libndk_translation)',
 'baseline_split_install_success':baseline_ok,
 'baseline_app_process_alive_after_launch':bool(os.environ.get('SHAREIT_BASELINE_PID','').strip()),
 'single_apk_install_success':single_ok,
 'single_apk_process_alive_after_launch':alive,
 'single_apk_default_launcher_success':os.environ.get('SHAREIT_DEFAULT_LAUNCH')=='1',
 'single_apk_alias_enabled_for_test':os.environ.get('SHAREIT_ALIAS_LAUNCH')=='1',
 'fatal_crash_during_single_test':bool(fatal_matches),
 'fatal_excerpt':fatal_matches[:2],
 'classloader_related_log_lines':[l[:500] for l in log.splitlines() if re.search(r'DexFile|DexPathList|ClassNotFound|Could not open dex|Failed to open dex|dex2oat|ZIP archive|base\\.apk',l,re.I)][-35:],
 'baseline_install_log_tail':bl[-400:],
 'single_install_log_tail':si[-400:],
 'ui_automator_xml_available':(d/'shareit-v2-ui.xml').exists(),
 'screenshot_available':(d/'shareit-v2-screen.png').exists(),
 'limitation':'Android 16 x86_64 emulator with ARM64 translation; UI screenshots taken but ad-free status requires manual visual inspection and network tests'
}
(d/'emulator-report.json').write_text(json.dumps(obj,indent=2))
print('ANDROID_RUNTIME_REPORT',json.dumps(obj))
if not single_ok or not alive or fatal_matches: raise SystemExit(7)
print('ANDROID_EMULATOR_INSTALL_AND_PROCESS_SURVIVAL=PASS')
PY
