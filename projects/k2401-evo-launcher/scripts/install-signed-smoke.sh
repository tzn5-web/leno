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
# Release intentionally ignores the debug-only k2401_skin_preview_ci intent.
# The old test passed that ignored extra and captured the SAME skin 8 times.
# Use ROOT ONLY ON THIS DISPOSABLE GOOGLE_APIS EMULATOR to set the genuine
# persisted skin preference between signed-production launches. Never use
# these commands on a user's head unit, phone or car.
adb root >/dev/null
adb wait-for-device
test "$(adb shell id -u | tr -d '\r')" = "0" || {
  echo "::error::Disposable Android emulator is not rootable; refusing fake multi-skin PASS"
  exit 7
}
mkdir -p k2401-glass-hud-signed-screens
for skin in 21 22 23 24 25 26 27 28; do
  python3 - "$skin" <<'PY'
import subprocess,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
app="ro.evolauncher.k2401"
skin=int(sys.argv[1])
path=f"/data/user/0/{app}/shared_prefs/evo_launcher_prefs.xml"
def adb(*args,check=True):
    return subprocess.run(["adb",*args],check=check,capture_output=True,text=True)
adb("shell","am","force-stop",app)
read=adb("shell","cat",path,check=False)
root=ET.fromstring(read.stdout) if read.returncode==0 and read.stdout.strip() else ET.Element("map")
for element in list(root):
    if element.attrib.get("name")=="selected_skin_v2":
        root.remove(element)
ET.SubElement(root,"int",name="selected_skin_v2",value=str(skin))
with tempfile.TemporaryDirectory() as temp:
    local=Path(temp)/"evo_launcher_prefs.xml"
    ET.ElementTree(root).write(local,encoding="utf-8",xml_declaration=True)
    tmp=f"/data/local/tmp/k2401-ci-skin-{skin}.xml"
    adb("push",str(local),tmp)
    uid=adb("shell","stat","-c","%u",f"/data/user/0/{app}").stdout.strip()
    assert uid.isdigit(),uid
    adb("shell","cp",tmp,path)
    adb("shell","chown",f"{uid}:{uid}",path)
    adb("shell","chmod","600",path)
    # Preserve the Android app-data SELinux label after an emulator-only copy.
    adb("shell","restorecon",path)
    adb("shell","rm",tmp)
    confirm=adb("shell","cat",path).stdout
    saved=ET.fromstring(confirm).find("./int[@name='selected_skin_v2']")
    assert saved is not None and saved.get("value")==str(skin),(skin,confirm)
print(f"K2401_SIGNED_RELEASE_ACTUAL_PERSISTED_SKIN={skin} PASS")
PY
  adb shell am start -W -n "$MAIN/ro.evolauncher.k2401.MainActivity" >/dev/null
  sleep 3
  adb shell pidof "$MAIN" >/dev/null
  if adb shell dumpsys window windows | grep -Eiq 'mCurrentFocus=.*(permissioncontroller|packageinstaller)'; then
    echo "::error::System dialog obscures signed skin $skin"
    exit 8
  fi
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
adb shell screencap -p /sdcard/k2401-evo-red-v118.png
adb pull /sdcard/k2401-evo-red-v118.png k2401-evo-red-v118-emulator.png >/dev/null
python3 - <<'PY'
from PIL import Image,ImageStat
im=Image.open("k2401-evo-red-v118-emulator.png").convert("RGB")
# Same -skin 720x1280 as the passing K2401 debug emulator workflow.
assert im.size==(1280,720),im.size
stat=ImageStat.Stat(im)
assert max(stat.stddev)>8,("Blank or nearly blank HUD",stat.stddev)
print("K2401_EVO_RED_V118_EMULATOR_SCREENSHOT=PASS actual_frame=",im.size)
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
