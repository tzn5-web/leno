# K2401 EVO – Azure emulator automation and audit

## Verified status (2026-10-26)

- GitHub Android 10 emulator CI previously passed: six real 1280x720 screenshots, cold relaunch, crash/ANR checks. This is **GitHub-hosted emulation**, not Azure.
- The dedicated Azure pipeline is installed on the repository's main branch as a **manual-only** GitHub Actions workflow:
  `.github/workflows/k2401-azure-emulator.yml`.
- Windows VM `int34d2-lab` in `rg-phaser360-driverlab` is deallocated and must remain off unless an authenticated test can execute.
- Azure ARM tool in this ChatGPT connection returned `MsalUiRequiredException / incremental consent`.
- Prior GitHub -> Azure access probe failed because an Azure client ID had not been configured for GitHub Actions.
- Windows PowerShell parser and GitHub actionlint passed in CI for the test workflow and script. **No real Azure VM emulator run has been executed yet.**
- APK is not a release: Home map remains a demo, the OBD emulator values are simulated, and YouTube Music / Torque / CANBUS interactions are not validated on hardware.

## One-time Azure -> GitHub workload identity (no permanent client secret)

The setup script targets a *dedicated* user-assigned Azure managed identity, not the existing chatgpt-azure-control identity. It creates a federated credential restricted to `repo:tzn5-web/leno:ref:refs/heads/main`, assigns **Virtual Machine Contributor** only on `int34d2-lab`, and **Storage Account Contributor** only within `rg-chatgpt-azure` to stage and delete temporary test artifacts.

In a user-authenticated **Azure Cloud Shell (Bash)**:

```bash
curl -fL 'https://raw.githubusercontent.com/tzn5-web/leno/feature/k2401-evo-launcher/projects/k2401-evo-launcher/scripts/bootstrap-azure-oidc.sh' -o bootstrap-k2401-oidc.sh
less bootstrap-k2401-oidc.sh
bash bootstrap-k2401-oidc.sh
```

If the Cloud Shell has an authenticated `gh` CLI, the script also sets the following *repository variables* automatically:
- `K2401_AZURE_CLIENT_ID`
- `K2401_AZURE_TENANT_ID`
- `K2401_AZURE_SUBSCRIPTION_ID`

Otherwise, copy the three printed non-secret IDs into GitHub repository **Settings -> Secrets and variables -> Actions -> Variables**.

Note: The interactive Azure session must have sufficient Azure RBAC and Entra consent rights to create the dedicated identity and federated credential. ChatGPT approval alone cannot bypass Azure's independent OAuth consent.

## Running the authenticated Azure test

Use [K2401 EVO Azure Android 10 emulator](https://github.com/tzn5-web/leno/actions/workflows/k2401-azure-emulator.yml) -> **Run workflow** from `main`. The workflow will:

1. Fail *before Azure resource startup* if any required repository variable is missing or OIDC login fails.
2. Build the APK with JDK 17/Gradle 8.11.1 and record SHA256.
3. Create a private **temporary** standard-LRS blob account and stage the APK behind a short-lived container SAS.
4. Refuse to touch the VM unless its initial power state is `deallocated`.
5. Start the existing Azure Windows VM, use `RunPowerShellScript` to install portable Android SDK/Android 10 emulator, verify transfer SHA256, run screen taps, collect PNG screenshots, logcat, memory and gfxinfo, and report test status.
6. Download the diagnostic images/logs into a GitHub Actions artifact.
7. **Always** attempt VM deallocation and deletion of the temporary storage account, even if tests fail. Retain Azure-native auto-shutdown as an additional failsafe.

The reusable VM test script intentionally avoids altering boot/MCU/CANBUS, changing Windows Hyper-V features, and touching the Phaser360 driver-lab project. Its isolated working directory is `C:\\K2401-EVO-LAB`.

## Cost guardrails

The existing Windows `Standard_D4s_v5` is listed at about **$0.388/hour** (Azure retail consumption, Sweden Central, checked 2026-10-26), excluding disks/network and ancillary services. The test is manually triggered, includes job and step timeouts, and deallocates the VM at the end. This is a cost estimate, not a spending guarantee.

## Release gate

Do not call the APK feature-complete until real Google Maps/YouTube Music/ELM327 telemetry integration is implemented and independently validated. An emulator cannot establish physical K2401 head-unit compatibility, reverse camera operation, steering-wheel controls, sound routing or CANBUS compatibility.
