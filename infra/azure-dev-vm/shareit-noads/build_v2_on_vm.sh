#!/bin/sh
# Read original SINGLE APK and Python patcher from private blob / source in Azure VM
# Runs under /bin/sh via Azure RunShellScript
set -eu
umask 077
W=/var/lib/shareit-noads/v2
mkdir -p "$W"
cd "$W"
test -s original.apk
test -s disable_ad_rendering.py
python3 disable_ad_rendering.py original.apk ad-disabled-unsigned.apk --report v2_audit.json
BT=/opt/android-sdk/build-tools/36.0.0
test -x "$BT/apksigner" && test -x "$BT/zipalign"
"$BT/zipalign" -f -P 16 4 ad-disabled-unsigned.apk ad-disabled-aligned.apk
KS=/var/lib/shareit-noads/signing.jks
PW=/var/lib/shareit-noads/keystore_password
test -s "$KS" && test -s "$PW"
PASS="$(cat "$PW")"
"$BT/apksigner" sign --ks "$KS" --ks-key-alias shareit-private \
  --ks-pass "pass:$PASS" --key-pass "pass:$PASS" --v2-signing-enabled true \
  --v3-signing-enabled true --out SHAREit_6.27.58_NoAds_v2_ARM64.apk ad-disabled-aligned.apk
unset PASS
"$BT/apksigner" verify --verbose SHAREit_6.27.58_NoAds_v2_ARM64.apk
"$BT/zipalign" -c -P 16 4 SHAREit_6.27.58_NoAds_v2_ARM64.apk
python3 - <<'PY'
import json,zipfile,hashlib,pathlib,struct,zlib
p=pathlib.Path('SHAREit_6.27.58_NoAds_v2_ARM64.apk')
r=pathlib.Path('v2_audit.json')
j=json.loads(r.read_text())
with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  dex=[n for n in z.namelist() if n.startswith('classes') and n.endswith('.dex')]
  assert len(dex)==10
  for n in dex:
    v=z.read(n)
    assert v.startswith(b'dex\n')
    assert v[12:32]==hashlib.sha1(v[32:]).digest()
    assert struct.unpack_from('<I',v,8)[0] == zlib.adler32(v[12:])&0xffffffff
    assert z.getinfo(n).compress_type==zipfile.ZIP_STORED
assert j['method_entrypoints_disabled']>=30
j.update({'sha256':hashlib.file_digest(open(p,'rb'),'sha256').hexdigest(),
          'bytes':p.stat().st_size,'dex_files':len(dex),
          'apksigner':'PASS','zipalign':'PASS','archive_integrity':'PASS',
          'runtime_validation':'PENDING',
          'advertising_warning':'Ad SDK method stubs; dynamic content/promoted cards and some ads could remain'})
r.write_text(json.dumps(j,indent=2))
print('AZURE_SHAREIT_V2_PATCH_AND_SIGN=PASS')
print('ADS_METHODS',j['method_entrypoints_disabled'])
print('OUTPUT_SHA256',j['sha256'])
PY
