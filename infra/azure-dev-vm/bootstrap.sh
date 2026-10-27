#!/usr/bin/env bash
# Ubuntu 24.04 VM bootstrap: Android SDK/Studio, Git, PowerShell, build stack.
# Idempotent: the completion marker is written only after validation.
set -Eeuo pipefail
exec > >(tee -a /var/log/android-dev-bootstrap.log) 2>&1
install -d -m 0755 /var/lib/android-dev
if [ -e /var/lib/android-dev/installed ]; then
  echo "ANDROID_DEV_BOOTSTRAP=ALREADY_INSTALLED"
  exit 0
fi
trap 'echo "ANDROID_DEV_BOOTSTRAP=FAILED line=$LINENO"; date -u +%FT%TZ > /var/lib/android-dev/failed' ERR
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=600 update
apt-get -o DPkg::Lock::Timeout=600 install -y --no-install-recommends \
  ca-certificates curl wget gnupg lsb-release unzip zip xz-utils tar git git-lfs gh \
  bash bash-completion openssh-server fail2ban jq tmux htop nano vim \
  python3 python3-pip python3-venv pipx nodejs npm \
  build-essential clang cmake ninja-build ccache pkg-config make maven \
  openjdk-17-jdk openjdk-21-jdk \
  lib32z1 lib32stdc++6 libglu1-mesa libxi6 libxrender1 libxtst6 libnss3 \
  snapd
git lfs install --system
# PowerShell from Microsoft's signed Ubuntu APT feed.
curl --fail --location --retry 5 --silent --show-error \
  https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb \
  -o /tmp/packages-microsoft-prod.deb
dpkg -i /tmp/packages-microsoft-prod.deb
apt-get -o DPkg::Lock::Timeout=600 update
apt-get -o DPkg::Lock::Timeout=600 install -y powershell
# Android SDK official Google CLI package, SHA256 pinned to upstream download page.
install -d -m 0755 /opt/android-sdk/cmdline-tools
curl --fail --location --retry 6 --retry-delay 8 --silent --show-error \
  https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip \
  -o /tmp/android-cmdline.zip
echo '4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583  /tmp/android-cmdline.zip' | sha256sum -c -
mkdir -p /tmp/android-cmdline-unpacked
unzip -q -o /tmp/android-cmdline.zip -d /tmp/android-cmdline-unpacked
mv /tmp/android-cmdline-unpacked/cmdline-tools /opt/android-sdk/cmdline-tools/latest
cat >/etc/profile.d/android-dev.sh <<'EOF'
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
export PATH=$PATH:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools
EOF
chmod 0644 /etc/profile.d/android-dev.sh
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
export PATH="$PATH:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools"
# sdkmanager can close its input before 'yes' finishes (SIGPIPE); validate afterwards.
(yes | sdkmanager --licenses >/var/log/android-sdk-licenses.log 2>&1) || true
sdkmanager --sdk_root=/opt/android-sdk \
  'platform-tools' 'platforms;android-36' 'platforms;android-35' \
  'build-tools;36.0.0' 'cmdline-tools;latest'
# Install Android Studio graphical IDE via snap; CLI SDK remains fully independent.
systemctl enable --now snapd.socket || true
snap install android-studio --classic
# Code can run remotely using SSH key auth, or from Github through Azure Run Command.
cat >/etc/ssh/sshd_config.d/99-android-dev.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
X11Forwarding yes
EOF
systemctl reload ssh
systemctl enable --now fail2ban
mkdir -p /home/dev/projects /home/dev/.gradle
chown -R dev:dev /home/dev/projects /home/dev/.gradle /opt/android-sdk
cat >/usr/local/bin/android-dev-status <<'EOF'
#!/usr/bin/env bash
set -e
git --version
gh --version | head -1
pwsh -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
java -version 2>&1 | head -1
/opt/android-sdk/cmdline-tools/latest/bin/sdkmanager --version
/opt/android-sdk/platform-tools/adb version | head -1
snap list android-studio
EOF
chmod +x /usr/local/bin/android-dev-status
/usr/local/bin/android-dev-status
date -u +%FT%TZ > /var/lib/android-dev/installed
rm -f /var/lib/android-dev/failed
echo "ANDROID_DEV_BOOTSTRAP=PASS"
