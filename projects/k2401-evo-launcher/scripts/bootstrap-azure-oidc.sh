#!/usr/bin/env bash
# K2401 EVO - ONE-TIME GitHub-to-Azure OIDC setup.
# Run in authenticated Azure Cloud Shell (Bash) as Azure subscription Owner.
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

if ! az identity show -g "$ID_RG" -n "$IDENTITY" >/dev/null 2>&1; then
  az identity create -g "$ID_RG" -n "$IDENTITY" -l "$LOCATION" -o none
fi
CLIENT_ID="$(az identity show -g "$ID_RG" -n "$IDENTITY" --query clientId -o tsv)"
PRINCIPAL_ID="$(az identity show -g "$ID_RG" -n "$IDENTITY" --query principalId -o tsv)"
[[ -n "$CLIENT_ID" && -n "$PRINCIPAL_ID" ]] || { echo 'IDENTITY_UNAVAILABLE'; exit 1; }

if ! az identity federated-credential show -g "$ID_RG" --identity-name "$IDENTITY" --name "$FIC" >/dev/null 2>&1; then
  az identity federated-credential create -g "$ID_RG" --identity-name "$IDENTITY" -n "$FIC" \
    --issuer 'https://token.actions.githubusercontent.com' \
    --subject "repo:$REPO:ref:refs/heads/main" \
    --audiences 'api://AzureADTokenExchange' -o none
fi

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
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  printf '%s' "$CLIENT_ID" | gh variable set K2401_AZURE_CLIENT_ID -R "$REPO"
  printf '%s' "$TENANT" | gh variable set K2401_AZURE_TENANT_ID -R "$REPO"
  printf '%s' "$SUB" | gh variable set K2401_AZURE_SUBSCRIPTION_ID -R "$REPO"
  echo "GITHUB_REPOSITORY_VARIABLES=SET"
else
  echo "GITHUB_REPOSITORY_VARIABLES=PENDING"
  echo "Enter the three values above in GitHub > Settings > Secrets and variables > Actions > Variables."
  echo "These three values are identifiers, not private keys."
fi
echo 'Only then dispatch K2401 EVO - Azure Android 10 emulator from GitHub Actions.'
