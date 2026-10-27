# Azure Linux Android development VM – DEPLOYED

## Verified state, 2026-10-27

The VM `android-dev-linux` was successfully created in subscription `0ac7a514-32b3-47bf-bf89-e17906b1cc86` and resource group `rg-chatgpt-azure`. Ubuntu Linux, location `eastus2`, Standard_E4as_v7 (4 vCPU, 32 GiB RAM), 128-GB StandardSSD OS disk, public IP `20.230.55.71`.

**Deployment result: PASS.** GitHub Actions run [40507749776](https://github.com/tzn5-web/leno/actions/runs/40507749776) completed successfully with `AZURE_ANDROID_DEV_SETUP=PASS`, and the VM was then deliberately `deallocated` to avoid compute charges. Linux is installed and persistent. The earlier Windows VM `int34d2-lab` was not altered.

Installed and validated in guest:
- Ubuntu 24.04 LTS, Git 2.43.0, GitHub CLI 2.45.0, Bash
- PowerShell `pwsh` 7.6.9
- Java JDK 17 and 21 (default Java reports 21.0.12.1)
- Android SDK command-line tools 22.0; Android platforms 35 and 36; ADB 1.0.41; Build Tools 36.0.0
- Android Studio 2026.2.1.8 (Snap `android-studio`, classic)
- Python, Python venv, Node.js/npm, Maven, CMake/Ninja, clang and other build essentials

The install was recovered from an interrupted cloud-init using the idempotent Linux systemd unit `android-dev-resume.service`. The SDK manager logged a **non-fatal** duplicate location warning for `cmdline-tools/latest-2` after successful installation; future bootstrap source no longer requests `cmdline-tools;latest`.

## Start and stop only when working

In [VM control workflow](https://github.com/tzn5-web/leno/actions/workflows/azure-android-dev-vm.yml), press **Run workflow**, choose `start` to allocate VM. Connect from Windows using the separate SSH kit, from its folder:

```powershell
.\CONNECT_WINDOWS.ps1 -Ip 20.230.55.71
```

Or directly: `ssh -i id_ed25519_azure_android_dev dev@20.230.55.71`.

When finished choose `deallocate`. A native Azure auto-shutdown schedule is set for 22:00 UTC. Compute cost stops after deallocation; SSD, public IP and other persistent resources still cost money. Azure Linux compute list price for this SKU in East US 2 was 0.238 USD/hour excluding storage/taxes. Never leave it running unnecessarily under the 200 USD Free Trial budget.

The VM has SSH key-only login, with password authentication and root SSH login disabled. The **private SSH key is not in GitHub**; protect it. GitHub holds only the public key. Access to Android Studio's graphical interface requires remote GUI/X11 (not configured); all headless SDK and Gradle builds can run via SSH.

## Repository configuration

- `infra/azure-dev-vm/bootstrap.sh`: idempotent tools installation.
- `infra/azure-dev-vm/cloud-init.yml`: OS initial bootstrap.
- `.github/workflows/azure-android-dev-vm.yml`: start/stop/provision/status.
- `.github/workflows/azure-android-vm-connection.yml`: IP and SSH checks.

The original Free Trial SKU capacity issues for other VM families/regions were diagnosed and worked around using an eligible East US 2 E4as v7 SKU; **no change of subscription offer** was required. Do not run the quota-request workflow for this VM.
