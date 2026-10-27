#!/usr/bin/env bash
# Personal-use private Azure build from the exact user-uploaded split APKS ZIP.
set -Eeuo pipefail
umask 077
READ_SAS="${1:?Requires input read SAS}"
WRITE_SAS="${2:?Requires output write SAS}"
BASE_URL=https://tzn5androidartifacts26.blob.core.windows.net/apks-private
WORK=/var/lib/shareit-azure/splitbuild
mkdir -p "$WORK/original" "$WORK/rebuilt" "$WORK/reports"
cd "$WORK"
curl --fail-with-body -sSL --connect-timeout 15 --max-time 350 \
 -o input.apks "${BASE_URL}/input/shareit-6.27.58-user.apks?${READ_SAS}"
echo "8dcbebc90086c6b1479364066b77bd62f7d2a768cc908799932ed2bdcb6a85fe  input.apks" | sha256sum --check --status
echo 'USER_APKS_ORIGINAL_SHA256=PASS'
unzip -t input.apks >/dev/null
python3 - <<'PY'
import zipfile, pathlib
with zipfile.ZipFile('input.apks') as z:
    entries=z.namelist()
    expected=[
      'base.apk','split_InnoPlayerDynamicFeature.apk',
      'split_InnoPlayerDynamicFeature.config.arm64_v8a.apk',
      'split_ModuleEntertainment.apk','split_ModuleOnline.apk',
      'split_config.arm64_v8a.apk']
    assert sorted(entries)==sorted(expected), ('Unexpected split layout', entries)
    for name in entries:
        (pathlib.Path('original')/name).write_bytes(z.read(name))
print("USER_APKS_SPLITS=6")
PY
ANDROID_TOOLS=/opt/android-sdk/build-tools/36.0.0
test -x "$ANDROID_TOOLS/apksigner"
test -x "$ANDROID_TOOLS/zipalign"
PATCH_PY=/tmp/shareit-patch-azure.py
curl --fail -fsSL --retry 3 \
 'https://raw.githubusercontent.com/tzn5-web/leno/65421b802344b63d5d07b25b11c1de1d73a279e5/infra/azure-dev-vm/shareit-patch.py' \
 -o "$PATCH_PY"
SIGN_DIR=/root/.config/shareit-azure-sign
mkdir -p "$SIGN_DIR"
if [ ! -s "$SIGN_DIR/signing.p12" ]; then
    openssl rand -hex 24 > "$SIGN_DIR/password"
    keytool -genkeypair -noprompt -alias azure-shareit -keyalg RSA -keysize 3072 \
       -validity 3650 -keystore "$SIGN_DIR/signing.p12" -storetype PKCS12 \
       -storepass "$(cat "$SIGN_DIR/password")" \
       -dname 'CN=Azure Android Personal Build,OU=Personal,O=Private,C=RO'
fi
TOTAL=0
for SRC in original/*.apk; do
  NAME="$(basename "$SRC")"
  "$ANDROID_TOOLS/apksigner" verify --print-certs "$SRC" > /tmp/original-cert.txt
  grep -Eiq 'bd102a94669896078db9c665b21bbd3d76691ff66ae97519a3634c34c3a02542' /tmp/original-cert.txt
  MD5="$(md5sum "$SRC" | awk '{print $1}')"
  python3 "$PATCH_PY" --source "$SRC" --expected-md5 "$MD5" \
    --output "$WORK/rebuilt/unsigned-$NAME" \
    --report "$WORK/reports/$NAME.json"
  "$ANDROID_TOOLS/zipalign" -f -p 4 "$WORK/rebuilt/unsigned-$NAME" "$WORK/rebuilt/aligned-$NAME"
  "$ANDROID_TOOLS/apksigner" sign --min-sdk-version 17 \
    --ks "$SIGN_DIR/signing.p12" --ks-key-alias azure-shareit \
    --ks-pass "file:$SIGN_DIR/password" --key-pass "file:$SIGN_DIR/password" \
    --out "$WORK/rebuilt/$NAME" "$WORK/rebuilt/aligned-$NAME"
  "$ANDROID_TOOLS/apksigner" verify --verbose "$WORK/rebuilt/$NAME" >/dev/null
  C="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["ad_host_occurrences_blocked"])' "$WORK/reports/$NAME.json")"
  TOTAL=$((TOTAL+C))
  echo "SIGN_SPLIT_PASS=$NAME BLOCKED=$C"
done
test "$TOTAL" -gt 10
"$ANDROID_TOOLS/aapt" dump badging rebuilt/base.apk | grep -q "name='com.lenovo.anyshare.gps'"
"$ANDROID_TOOLS/aapt" dump badging rebuilt/base.apk | grep -q "versionCode='4062758'"
python3 - <<'PY'
import zipfile, pathlib, json
names=[
  'base.apk','split_InnoPlayerDynamicFeature.apk',
  'split_InnoPlayerDynamicFeature.config.arm64_v8a.apk',
  'split_ModuleEntertainment.apk','split_ModuleOnline.apk',
  'split_config.arm64_v8a.apk']
with zipfile.ZipFile('SHAREit_6.27.58_Azure_NoAds_Splits.apks','w',compression=zipfile.ZIP_STORED) as out:
    for name in names:
        out.write(pathlib.Path('rebuilt')/name, arcname=name)
with zipfile.ZipFile('SHAREit_6.27.58_Azure_NoAds_Splits.apks') as z:
    assert set(z.namelist()) == set(names)
    assert z.testzip() is None
print("SPLIT_APKS_ARCHIVE_INTEGRITY=PASS")
PY
curl --fail-with-body -sS --retry 3 --retry-all-errors --max-time 320 \
 -X PUT -H 'x-ms-blob-type: BlockBlob' -H 'Content-Type: application/zip' \
 --upload-file SHAREit_6.27.58_Azure_NoAds_Splits.apks \
 "${BASE_URL}/output/shareit-6.27.58-azure-nosads-splits.apks?${WRITE_SAS}" >/dev/null
echo 'AZURE_USER_SHAREIT_SIX_SPLITS_UPLOAD=PASS'
echo "AD_HOST_REFERENCES_NEUTRALIZED=$TOTAL"
sha256sum SHAREit_6.27.58_Azure_NoAds_Splits.apks
echo 'AZURE_SHAREIT_USER_SPLITS_BUILD=PASS'
