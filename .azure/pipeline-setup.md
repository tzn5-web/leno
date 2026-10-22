# GitHub <-> Azure bridge — policy and bootstrap

Scope: this repository's iOS app is NOT part of the Azure driver work. This directory only hosts an opt-in, read-only GitHub Actions/Azure bridge. No audio, SOF, DSP, codec, or iOS application code is modified by this integration.

## Verified inventory (22 Oct 2026)

- GitHub repo: `tzn5-web/leno` (public), repository ID `1404038746`, owner ID `331569227`, main branch `main`.
- Azure subscription: obtain dynamically using `az account show`; never put account tokens or passwords into the repository.
- Existing auth/control resource group: `rg-chatgpt-azure` in Sweden Central.
- Existing driver-lab resource group: `rg-phaser360-driverlab`; VM `int34d2-lab` was `deallocated`.
- Existing `chatgpt-azure-identity` belongs to the control application. Do not reuse its permissions for the GitHub pipeline.

## Design

- GitHub owns source code, version history, audits and CI; Azure is optional and only used when necessary.
- `.github/workflows/azure-readonly.yml`: **manual** `workflow_dispatch` plus `workflow_call` for future projects. It does not trigger on push or PR.
- Azure authentication: short-lived GitHub Actions OIDC, `azure/login@v3`. Never store a client secret, password, PAT or service-principal JSON.
- Dedicated user-assigned managed identity `github-leno-readonly`. Assign only built-in `Reader` at `/resourceGroups/rg-phaser360-driverlab` scope. Reader cannot power on a VM.
- The workflow does not call `az vm start`, `az vm deallocate`, `az deployment`, `az identity`, or other mutation commands.
- **Azure budget ceiling: USD 200**. No VM starts, deployments, new paid compute, or permanent service expansions without explicit user approval. A deallocated VM can still have disk/network costs.
- Limit jobs to five minutes; manual Azure inventory uses GitHub-hosted runner minutes, which may be billed under GitHub plan quotas.
- Do not change the repaired audio stack. All driver/power hardware tests require a separate explicit authorization.

## Finish GitHub/Azure OIDC trust (not provisioned by merely committing this file)

Run `.azure/setup-azure-oidc.sh --apply` from a machine with `az` and `gh` authenticated and the permissions to create a federated credential, assign Reader, and set GitHub Actions secrets. **It does not start the VM**. Review the script before running.

The script:

1. Checks that the control and driver-lab resource groups already exist.
2. Creates a separate user-assigned managed identity, if missing, in the existing control resource group.
3. Adds GitHub OIDC federated trust for the `main` branch of this repository.
4. Grants only Azure Reader on the existing driver-lab resource group.
5. Adds `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` as encrypted GitHub Actions repository secrets.

Since this repository was created on October 4, 2026, GitHub's newer **immutable OIDC subject** normally applies. The federated subject is:

```text
repo:tzn5-web@331569227/leno@1404038746:ref:refs/heads/main
```

If customized OIDC claim settings have been enabled, verify the actual `sub` claim before configuring Azure; a mismatched subject prevents login. Issuer is `https://token.actions.githubusercontent.com`, audience is `api://AzureADTokenExchange`.

After configuring trust, open **Actions > Azure inventory - read only > Run workflow** and inspect `rg-phaser360-driverlab`/`int34d2-lab`. This read-only run is the verification of the connection. Until it succeeds, the integration is **STAGED, not VERIFIED**.

## Future projects

Reuse the centralized workflow from a project-specific repository:

```yaml
name: Check Azure resources
on:
  workflow_dispatch:
permissions:
  contents: read
  id-token: write
jobs:
  inventory:
    uses: tzn5-web/leno/.github/workflows/azure-readonly.yml@main
    with:
      resource_group: rg-your-project
      vm_name: ''
    secrets: inherit
```

Each future **caller repository** requires its own trusted OIDC subject and appropriately scoped Azure identity/secrets. Do not reuse `leno`'s trust or broad Azure permissions blindly; the GitHub OIDC token in a reusable workflow represents its caller. Prefer a private repository for future non-public projects and pin reusable workflows to a reviewed commit SHA.

Sources:
- https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect
- https://docs.github.com/en/actions/reference/security/oidc
- https://github.com/Azure/login

Status: GitHub workflow committed; Azure federated trust and GitHub secrets must still be configured and verified. No Azure compute was started during setup.
