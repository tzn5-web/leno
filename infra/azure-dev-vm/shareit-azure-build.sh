#!/usr/bin/env bash
# Runs exclusively inside the user's Azure Ubuntu VM.
# The APK itself is never checked into public source control.
set -Eeuo pipefail
umask 077
SAS="${1:?Private single-object write SAS required}"
STORAGE_URL="https://tzn5androidartifacts26.blob.core.windows.net/apks-private/shareit-6.27.58-azure-nosads-arm64.apk"
ORIG_URL="https://s-06.filesincloud.com/storage/24/637/16637/arm64_v8a/74c64f8ff3ac6507730cd6659315883d/SHAREit-6.27.58_ww.apk?s=QLoDYLinUp9KuPLVEehb0g&e=1793171366&lang=en&apk_id=16122&premium_speed=0"
WORK="/var/lib/shareit-azure"
mkdir -p "$WORK"
cd "$WORK"
echo 'AZURE_SHAREIT_DOWNLOAD_ORIGINAL=START'
curl -fL --retry 2 --retry-all-errors --connect-timeout 15 --max-time 420 \
  --user-agent 'Mozilla/5.0 (Linux; Android 14)' --output original.apk "$ORIG_URL"
test "$(stat -c%s original.apk)" -eq 65502678
test "$(md5sum original.apk | awk '{print $1}')" = '74c64f8ff3ac6507730cd6659315883d'
echo 'AZURE_SHAREIT_ORIGINAL_MD5=PASS'
BUILD_TOOLS="/opt/android-sdk/build-tools/36.0.0"
if [ ! -x "$BUILD_TOOLS/apksigner" ] || [ ! -x "$BUILD_TOOLS/zipalign" ]; then
  echo 'ANDROID_BUILD_TOOLS_NOT_INSTALLED'
  exit 4
fi
"$BUILD_TOOLS/apksigner" verify --print-certs original.apk > original-cert.txt
grep -Eiq 'bd102a94669896078db9c665b21bbd3d76691ff66ae97519a3634c34c3a02542' original-cert.txt || {
 echo 'SOURCE_CERTIFICATE_MISMATCH'
 exit 7
}
echo 'AZURE_SHAREIT_OFFICIAL_SIGNER=PASS'
curl -fLsS --retry 3 \
 'https://raw.githubusercontent.com/tzn5-web/leno/f856539a4517537288dbf0aaf796cbf33d822fe5/infra/azure-dev-vm/shareit-patch.py' \
 -o patch.py
python3 patch.py --source original.apk --output unsigned.apk --report patch-report.json
test "$(python3 -c 'import json;print(json.load(open("patch-report.json"))["ad_host_occurrences_blocked"])')" -gt 10
"$BUILD_TOOLS/zipalign" -f -p 4 unsigned.apk aligned.apk
SIGN_DIR=/root/.config/shareit-azure-sign
mkdir -p "$SIGN_DIR"
if [ ! -f "$SIGN_DIR/signing.p12" ]; then
  openssl rand -hex 24 > "$SIGN_DIR/password"
  keytool -genkeypair -noprompt -alias azure-shareit -keyalg RSA -keysize 3072 \
      -validity 3650 -keystore "$SIGN_DIR/signing.p12" -storetype PKCS12 \
      -storepass "$(cat "$SIGN_DIR/password")" \
      -dname 'CN=Azure Android Personal Build,OU=Personal,O=Private,C=RO'
fi
"$BUILD_TOOLS/apksigner" sign --min-sdk-version 17 \
  --ks "$SIGN_DIR/signing.p12" --ks-key-alias azure-shareit \
  --ks-pass "file:$SIGN_DIR/password" --key-pass "file:$SIGN_DIR/password" \
  --out SHAREit_6.27.58_Azure_NoAds_ARM64.apk aligned.apk
"$BUILD_TOOLS/zipalign" -c -v 4 SHAREit_6.27.58_Azure_NoAds_ARM64.apk > zipalign-report.txt
"$BUILD_TOOLS/apksigner" verify --verbose --print-certs SHAREit_6.27.58_Azure_NoAds_ARM64.apk > apkverify-report.txt
"$BUILD_TOOLS/aapt" dump badging SHAREit_6.27.58_Azure_NoAds_ARM64.apk > badging.txt
grep -q "name='com.lenovo.anyshare.gps'" badging.txt
grep -q "versionCode='4062758'" badging.txt
echo 'AZURE_SHAREIT_REBUILD_SIGN_VERIFY=PASS'
# HTTPS-only single-blob SAS, created at run time by GitHub Azure OIDC.
# Never echo SAS token into logs.
curl --fail-with-body --silent --show-error --retry 3 --retry-all-errors \
 --connect-timeout 15 --max-time 320 \
 -X PUT -H 'x-ms-blob-type: BlockBlob' \
 -H 'Content-Type: application/vnd.android.package-archive' \
 --upload-file SHAREit_6.27.58_Azure_NoAds_ARM64.apk "${STORAGE_URL}?${SAS}" >/dev/null
echo "AZURE_SHAREIT_PRIVATE_BLOB_UPLOAD=PASS"
sha256sum SHAREit_6.27.58_Azure_NoAds_ARM64.apk
echo 'AZURE_SHAREIT_WORKFLOW=PASS'
