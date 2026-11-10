#!/usr/bin/env bash
# Sign a reconstructed Xiaomi LatinIME APK ONLY if it can update the
# previously-installed working APK. No keystore or passwords in GitHub.
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "Usage: sign_and_verify_update.sh existing-signed.apk rebuilt-unsigned.apk signing.jks alias output.apk" >&2
  exit 2
fi
BASE="$1"; UNSIGNED="$2"; STORE="$3"; ALIAS="$4"; OUTPUT="$5"
[[ -v S24_APK_KS_PASSWORD && -v S24_APK_KEY_PASSWORD ]] || {
  echo "Set environment variables S24_APK_KS_PASSWORD and S24_APK_KEY_PASSWORD" >&2; exit 2;
}
for file in "$BASE" "$UNSIGNED" "$STORE"; do
  [[ -f "$file" ]] || { echo "Missing required file: $file" >&2; exit 2; }
done
[[ "$OUTPUT" != "$BASE" && "$OUTPUT" != "$UNSIGNED" && ! -e "$OUTPUT" ]] || {
  echo "Refusing to overwrite existing APKs" >&2; exit 2;
}
SDK="$(printenv ANDROID_HOME || printenv ANDROID_SDK_ROOT || true)"
[[ -n "$SDK" ]] || { echo "Set ANDROID_HOME to installed Android SDK" >&2; exit 2; }
TOOLS="$(find "$SDK/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
APKSIGNER="$TOOLS/apksigner"; ZIPALIGN="$TOOLS/zipalign"; AAPT="$TOOLS/aapt2"
for executable in "$APKSIGNER" "$ZIPALIGN" "$AAPT"; do
  [[ -x "$executable" ]] || { echo "Missing build tool: $executable" >&2; exit 2; }
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
baseline="$("$APKSIGNER" verify --verbose --print-certs "$BASE")" || {
  echo "Previous working APK signature is invalid" >&2; exit 3;
}
oldcert="$(printf '%s\n' "$baseline" | grep -Eo '[[:xdigit:]]{64}' | head -1 || true)"
[[ "$oldcert" =~ ^[[:xdigit:]]{64}$ ]] || {
  echo "Unable to extract baseline signing certificate SHA256" >&2
  printf '%s\n' "$baseline" | grep -Ei 'signer|certificate|SHA-256' >&2 || true
  exit 3;
}

"$ZIPALIGN" -f -p 4 "$UNSIGNED" "$tmp/aligned.apk"
"$APKSIGNER" sign --ks "$STORE" --ks-key-alias "$ALIAS" \
  --ks-pass env:S24_APK_KS_PASSWORD --key-pass env:S24_APK_KEY_PASSWORD \
  --out "$tmp/signed.apk" "$tmp/aligned.apk"
newcert="$("$APKSIGNER" verify --verbose --print-certs "$tmp/signed.apk" |
  grep -Eo '[[:xdigit:]]{64}' | head -1 || true)"
if [[ "$oldcert" != "$newcert" ]]; then
  echo "BLOCKED: certificate mismatch — this would not update the installed keyboard" >&2
  echo "Current certificate SHA256: $oldcert" >&2
  echo "New certificate SHA256:     $newcert" >&2
  exit 4
fi

oldpkg="$("$AAPT" dump badging "$BASE" |
  sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -1)"
newbadging="$("$AAPT" dump badging "$tmp/signed.apk")"
newpkg="$(printf '%s\n' "$newbadging" |
  sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -1)"
[[ -n "$oldpkg" && "$oldpkg" == "$newpkg" ]] || {
  echo "BLOCKED: APK package identity mismatch" >&2; exit 5;
}
oldver="$("$AAPT" dump badging "$BASE" |
  sed -n "s/^package:.*versionCode='\([0-9]*\)'.*/\1/p" | head -1)"
newver="$(printf '%s\n' "$newbadging" |
  sed -n "s/^package:.*versionCode='\([0-9]*\)'.*/\1/p" | head -1)"
if [[ -n "$oldver" && -n "$newver" ]] && (( newver < oldver )); then
  echo "BLOCKED: APK versionCode would downgrade the installed version" >&2
  exit 6
fi

"$ZIPALIGN" -c -p 4 "$tmp/signed.apk"
if printf '%s\n' "$newbadging" |
  grep -Eq '^(uses-permission:|uses-permission-sdk-23:)'; then
  echo "BLOCKED: unexpected Android permissions requested" >&2
  exit 7
fi

mv -- "$tmp/signed.apk" "$OUTPUT"
echo "PASS: same signer, Android package, valid version and zero manifest permissions"
echo "Package: $newpkg"
echo "Certificate SHA256: $newcert"
echo "Output: $OUTPUT"
echo "NOTE: runtime on Samsung One UI is still a separate release gate."
