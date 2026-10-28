#!/bin/sh
# GitHub OIDC starts the dedicated Azure Ubuntu VM, then runs this script through Azure VM Run Command.
# Posix shell is required: Azure RunShellScript invokes /bin/sh (dash) by default.
set -eu
umask 077
AZURE_UPLOAD_URL="$1"
GIT_SHA="$2"
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
install -d -m 0700 /var/lib/velolink-offline
if [ ! -x /opt/gradle-8.11.1/bin/gradle ]; then
  curl -fsSL --retry 3 https://services.gradle.org/distributions/gradle-8.11.1-bin.zip -o /tmp/gradle-8.11.1-bin.zip
  curl -fsSL --retry 3 https://services.gradle.org/distributions/gradle-8.11.1-bin.zip.sha256 -o /tmp/gradle-8.11.1-bin.zip.sha256
  echo "$(cat /tmp/gradle-8.11.1-bin.zip.sha256)  /tmp/gradle-8.11.1-bin.zip" | sha256sum -c -
  unzip -oq /tmp/gradle-8.11.1-bin.zip -d /opt
fi
if [ ! -d /var/lib/velolink-offline/source/.git ]; then
  git clone --filter=blob:none --no-checkout https://github.com/tzn5-web/leno.git /var/lib/velolink-offline/source
  git -C /var/lib/velolink-offline/source sparse-checkout set projects/velolink-offline
fi
git -C /var/lib/velolink-offline/source fetch --depth 1 origin "$GIT_SHA"
git -C /var/lib/velolink-offline/source checkout -f "$GIT_SHA"
cd /var/lib/velolink-offline/source/projects/velolink-offline
if ! /opt/gradle-8.11.1/bin/gradle --no-daemon :app:assembleDebug > /var/lib/velolink-offline/build.log 2>&1; then
  tail -n 85 /var/lib/velolink-offline/build.log
  exit 31
fi
FILE=app/build/outputs/apk/debug/app-debug.apk
test -s "$FILE"
sha256sum "$FILE"
curl -fsSL --retry 3 --max-time 150 -X PUT -H 'x-ms-blob-type: BlockBlob' --data-binary @"$FILE" "$AZURE_UPLOAD_URL" >/dev/null
echo VELOLINK_AZURE_BUILD_UPLOAD_PASS
