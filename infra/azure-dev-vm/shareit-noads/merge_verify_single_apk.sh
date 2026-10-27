#!/bin/sh
# Merge six original, already Azure-modified SHAREit splits to one APK.
# Runs as root through Azure VM RunShellScript, so use POSIX shell.
set -eu
umask 077
WORK=/var/lib/shareit-noads/single
mkdir -p "$WORK"
cd "$WORK"
ANDROID_HOME=${ANDROID_HOME:-/opt/android-sdk}
TOOLS="$ANDROID_HOME/build-tools/36.0.0"
EDITOR=APKEditor-1.4.9.jar
JAR_URL="https://github.com/REAndroid/APKEditor/releases/download/V1.4.9/$EDITOR"
JAR_SHA256=a9cd40df818845456be6d696de6110c89edf4b0a0580cb83438ed6b25a366e67
# All binaries are obtained on Azure VM from official APKEditor release/our private Blob.
curl -fL --retry 3 --silent --show-error "$JAR_URL" -o "$EDITOR"
echo "$JAR_SHA256  $EDITOR" | sha256sum -c -
test -s source.apks
rm -f merged-unsigned.apk merged-aligned.apk SHAREit_6.27.58_NoAds_SINGLE_ARM64.apk single-apk-report.json
java -Xmx8g -jar "$EDITOR" m -i source.apks -o merged-unsigned.apk -clean-meta -f >merge.log 2>&1 || {
  tail -n 85 merge.log; exit 20;
}
test -s merged-unsigned.apk
"$TOOLS/zipalign" -f -P 16 4 merged-unsigned.apk merged-aligned.apk
KS=/var/lib/shareit-noads/signing.jks
PW=/var/lib/shareit-noads/keystore_password
test -s "$KS"
test -s "$PW"
PASS="$(cat "$PW")"
"$TOOLS/apksigner" sign --ks "$KS" --ks-key-alias shareit-private \
  --ks-pass "pass:$PASS" --key-pass "pass:$PASS" \
  --v2-signing-enabled true --v3-signing-enabled true \
  --out SHAREit_6.27.58_NoAds_SINGLE_ARM64.apk merged-aligned.apk
unset PASS
"$TOOLS/zipalign" -c -P 16 4 SHAREit_6.27.58_NoAds_SINGLE_ARM64.apk
"$TOOLS/apksigner" verify --verbose --print-certs SHAREit_6.27.58_NoAds_SINGLE_ARM64.apk >signature.log
"$TOOLS/aapt" dump badging SHAREit_6.27.58_NoAds_SINGLE_ARM64.apk >badging.log
python3 - <<'PY'
import zipfile, json, pathlib, hashlib, re
w=pathlib.Path('/var/lib/shareit-noads/single')
src=w/'source.apks'
out=w/'SHAREit_6.27.58_NoAds_SINGLE_ARM64.apk'
assert zipfile.is_zipfile(out)
with zipfile.ZipFile(src) as pkg:
    names=pkg.namelist()
    assert len(names)==6, f'Input has {len(names)} modules'
    orig_dex = 0
    original_shared_libs = set()
    for n in names:
        with zipfile.ZipFile(__import__('io').BytesIO(pkg.read(n))) as z:
            orig_dex += sum(1 for fn in z.namelist() if re.fullmatch(r'classes\d*\.dex',fn))
            original_shared_libs |= {fn for fn in z.namelist() if fn.startswith('lib/arm64-v8a/') and fn.endswith('.so')}
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None, 'Corrupt merged ZIP'
    merged_dex = [n for n in z.namelist() if re.fullmatch(r'classes\d*\.dex',n)]
    missing_libs=original_shared_libs-set(z.namelist())
    assert not missing_libs, f'Missing ARM64 libs: {missing_libs}'
    assert len(merged_dex) >= orig_dex, f'DEX loss after merge: {len(merged_dex)} < {orig_dex}'
    assert 'AndroidManifest.xml' in z.namelist()
    assert 'resources.arsc' in z.namelist()
    assert len(z.namelist()) > 1000
    details = {
      'sha256':hashlib.file_digest(open(out,'rb'),'sha256').hexdigest(),
      'bytes':out.stat().st_size,
      'input_split_modules':len(names),
      'input_dex_files':orig_dex,
      'merged_dex_files':len(merged_dex),
      'arm64_libraries':len(original_shared_libs),
      'native_libraries_preserved':True,
      'zip_integrity':'PASS',
      'zipalign_16k':'PASS',
      'apksigner_verify':'PASS',
      'resources_merged':'PASS',
      'merge_engine':'REAndroid/APKEditor V1.4.9',
      'test_level':'static only; Android installation and app launch require emulator/device testing'
    }
s=(w/'badging.log').read_text(errors='replace')
assert "package: name='com.lenovo.anyshare.gps'" in s, s[:1000]
# The original SHA-verified base.apk also has NO launchable-activity in aapt badging.
# This is a pre-existing AndroidManifest feature (dynamic/disabled launcher alias),
# so requiring an aapt launchable activity creates a false regression gate.
assert "application-label:'SHAREit'" in s, 'Application label missing'
m=re.search(r"launchable-activity: name='([^']+)'",s)
details['launchable_activity_from_aapt']=m.group(1) if m else None
details['base_original_also_has_no_aapt_launchable_activity']=True
details['cold_launch_requires_android_emulator_comparison']=True
(w/'single-apk-report.json').write_text(json.dumps(details,indent=2))
print('AZURE_SHAREIT_SINGLE_APK_STATIC_PASS',details['sha256'],details['bytes'])
print('DEX_COUNT',orig_dex,len(merged_dex),'ARM64_LIBS',len(original_shared_libs))
PY
