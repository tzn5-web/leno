# Azure Android development VM

The project prepares a dedicated Ubuntu 24.04 Linux VM with the official Android SDK, Android Studio snap, Git, GitHub CLI, PowerShell, Bash, JDK 17/21, Python, Node.js, CMake, and build dependencies.

## Deployment state (2026-10-27)

**Not provisioned yet.** Azure OIDC authentication passed in GitHub Actions. Azure rejected all VM creations with:
- `RequestDisallowedByAzure` in West Europe (subscription ineligible for this region).
- `QuotaExceeded` in Sweden Central: region-wide limit **4 cores**, **4 used** by the existing deallocated Windows VM `int34d2-lab`, +4 needed for proposed Linux VM; request limit **8**. The existing VM is untouched.
- `SkuNotAvailable` capacity errors for D4, E2, B2as and D2 VM SKUs across UK South, North Europe, France Central, Germany West Central, and East US.

The action is now **manual-only** and will NOT create VMs automatically on GitHub pushes.

## Owner prerequisite

Open Azure portal **Subscriptions > Azure subscription 1 > Usage + quotas > Compute**, select **Sweden Central**, and request total regional cores raised from 4 to **8**. This is a quota approval request, not a VM purchase. A larger quota does not guarantee capacity, so the provisioning workflow tries multiple sizes/regions.

## After the quota request is approved

Go to GitHub Actions > `Azure Android Linux development VM (one-time provision, budget guarded)` > Run workflow > operation `provision`. The workflow will use the already configured GitHub OIDC identity, select the first eligible VM in its list (including Sweden Central Standard_D4s_v5), install all tools with cloud-init, validate binaries and **deallocate** after provisioning whether successful or failed. To use it later, Run workflow with `start`; to release hourly compute, select `deallocate`. The Azure native auto-shutdown is set to 22:00 UTC.

This deployment creates a 128-GB Standard SSD disk (storage billing persists while VM is deallocated) and, on success, a public IP + virtual network. VM compute is billed while allocated, even if no one is logged in. Monitor the subscription budget and remaining trial credit.

## SSH

The VM is configured for SSH-key authentication only, user `dev`. The **private** SSH key is NOT committed to the repository; the user needs the local SSH kit produced separately to connect. Never upload that key to GitHub.

Android Studio graphical IDE requires a desktop/X11 session to display; for headless workloads use the installed `sdkmanager`, `gradlew`, and Java tools. Emulators may require nested virtualization that is not guaranteed on the selected VM family.
