#!/usr/bin/env bash
# K2401 EVO - idempotent permanent GitHub-to-Azure OIDC repair.
# Run once in the account owner's Azure Cloud Shell. Re-running only repairs drift.
# Restricts roles to the pre-existing VM and control resource group; never grants subscription Owner.
set -euo pipefail

SUB="0ac7a514-32b3-47bf-bf89-e17906b1cc86"
TENANT="779623db-ec2e-495b-9828-85d42baa77ee"
ID_RG="rg-chatgpt-azure"
VM_RG="rg-phaser360-driverlab"
VM_NAME="int34d2-lab"
IDENTITY="k2401-github-oidc"
REPO="tzn5-web/leno"
LOCATION="swedencentral"
FIC="github-main-k2401-evo"

az account set --subscription "$SUB"
echo "Current tenant/subscription:"
az account show --query '{tenantId:tenantId,subscription:id}' -o json
ACTUAL_TENANT="$(az account show --query tenantId -o tsv)"
[[ "$ACTUAL_TENANT" == "$TENANT" ]] || { echo "TENANT_MISMATCH: no changes made"; exit 2; }

# Required for creating the short-lived APK transfer account. Fresh Azure subscriptions
# often lack this resource-provider registration; Storage Account Contributor on an RG
# cannot register providers at subscription scope. Run as the subscription owner.
STORAGE_PROVIDER_STATE="$(az provider show --namespace Microsoft.Storage --query registrationState -o tsv)"
if [[ "$STORAGE_PROVIDER_STATE" != 'Registered' ]]; then
  echo "REGISTERING_MICROSOFT_STORAGE_PROVIDER: $STORAGE_PROVIDER_STATE"
  az provider register --namespace Microsoft.Storage --wait
fi
STORAGE_PROVIDER_STATE="$(az provider show --namespace Microsoft.Storage --query registrationState -o tsv)"
[[ "$STORAGE_PROVIDER_STATE" == 'Registered' ]] || { echo "MICROSOFT_STORAGE_PROVIDER_NOT_REGISTERED=$STORAGE_PROVIDER_STATE"; exit 5; }
echo 'MICROSOFT_STORAGE_PROVIDER=PASS'

# Identity already exists. Do not create a duplicate or increase permissions.
if ! az identity show -g "$ID_RG" -n "$IDENTITY" >/dev/null 2>&1; then
  echo 'IDENTITY_NOT_FOUND: stop and investigate; do not create a replacement.'
  exit 2
fi
CLIENT_ID="$(az identity show -g "$ID_RG" -n "$IDENTITY" --query clientId -o tsv)"
PRINCIPAL_ID="$(az identity show -g "$ID_RG" -n "$IDENTITY" --query principalId -o tsv)"
[[ -n "$CLIENT_ID" && -n "$PRINCIPAL_ID" ]] || { echo 'IDENTITY_UNAVAILABLE'; exit 1; }
[[ "$CLIENT_ID" == '50a5c260-15a0-4aa0-9e02-5f0ad5c23df9' ]] || { echo 'WRONG_MANAGED_IDENTITY_CLIENT_ID'; exit 2; }

# GitHub repositories created after July 15 2026 use an immutable OIDC subject
# containing owner/repository IDs. Match the subject recorded in the CI login error.
FIC_SUBJECT='repo:tzn5-web@331569227/leno@1404038746:ref:refs/heads/main'
CURRENT_SUBJECT="$(az identity federated-credential show -g "$ID_RG" --identity-name "$IDENTITY" --name "$FIC" --query subject -o tsv 2>/dev/null || true)"
if [[ -z "$CURRENT_SUBJECT" ]]; then
  az identity federated-credential create -g "$ID_RG" --identity-name "$IDENTITY" -n "$FIC" \
    --issuer 'https://token.actions.githubusercontent.com' \
    --subject "$FIC_SUBJECT" \
    --audiences 'api://AzureADTokenExchange' -o none
elif [[ "$CURRENT_SUBJECT" != "$FIC_SUBJECT" ]]; then
  az identity federated-credential update -g "$ID_RG" --identity-name "$IDENTITY" -n "$FIC" \
    --issuer 'https://token.actions.githubusercontent.com' \
    --subject "$FIC_SUBJECT" \
    --audiences 'api://AzureADTokenExchange' -o none
fi
ACTUAL_SUBJECT="$(az identity federated-credential show -g "$ID_RG" --identity-name "$IDENTITY" --name "$FIC" --query subject -o tsv)"
[[ "$ACTUAL_SUBJECT" == "$FIC_SUBJECT" ]] || { echo 'OIDC_SUBJECT_MISMATCH'; exit 4; }
echo 'AZURE_OIDC_FEDERATION_SUBJECT=PASS'

VM_SCOPE="$(az vm show -g "$VM_RG" -n "$VM_NAME" --query id -o tsv)"
STORAGE_SCOPE="/subscriptions/$SUB/resourceGroups/$ID_RG"
function ensure_role() {
  local scope="$1" role="$2" role_count
  role_count="$(az role assignment list --assignee "$PRINCIPAL_ID" --scope "$scope" --role "$role" --query 'length(@)' -o tsv 2>/dev/null || echo 0)"
  if [[ "$role_count" == '0' ]]; then
    for attempt in 1 2 3 4 5; do
      if az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
          --scope "$scope" --role "$role" -o none; then break; fi
      if [[ "$attempt" == 5 ]]; then echo "ROLE_ASSIGNMENT_FAILED: $role"; exit 3; fi
      sleep 10
    done
  fi
}
# VM rights restricted to exactly this VM (start / run-command / deallocate).
ensure_role "$VM_SCOPE" 'Virtual Machine Contributor'
# Only storage-account management in the small control resource group.
ensure_role "$STORAGE_SCOPE" 'Storage Account Contributor'

printf '\nAZURE_OIDC_SETUP=PASS\n'
printf 'K2401_AZURE_CLIENT_ID=%s\n' "$CLIENT_ID"
printf 'K2401_AZURE_TENANT_ID=%s\n' "$TENANT"
printf 'K2401_AZURE_SUBSCRIPTION_ID=%s\n' "$SUB"
printf '\n'
echo 'GitHub workflow now embeds the three non-secret IDs; no repository variables are needed.'
echo 'OIDC_FEDERATION_READY=PASS'
