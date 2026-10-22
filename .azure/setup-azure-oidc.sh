#!/usr/bin/env bash
# Explicit, one-time OIDC bootstrap. No VM start, no paid compute provisioning.
set -euo pipefail

REPO='tzn5-web/leno'
CONTROL_RG='rg-chatgpt-azure'
DRIVER_RG='rg-phaser360-driverlab'
LOCATION='swedencentral'
IDENTITY_NAME='github-leno-readonly'
FEDERATION_NAME='leno-main-readonly'
OIDC_SUBJECT='repo:tzn5-web@331569227/leno@1404038746:ref:refs/heads/main'

if [[ "${1:-}" != '--apply' ]]; then
  echo 'DRY RUN: no changes made.'
  echo 'To connect the repo after reviewing this script, run: bash .azure/setup-azure-oidc.sh --apply'
  echo 'Planned operations: create dedicated identity only if absent; OIDC trust; Reader scope; GitHub encrypted secrets.'
  echo 'No VM start, no Azure paid compute, no driver/audio/iOS modifications.'
  exit 0
fi

for program in az gh; do
  if ! command -v "$program" >/dev/null 2>&1; then
    echo "Required executable missing: $program" >&2
    exit 1
  fi
done

az account show >/dev/null
gh auth status >/dev/null

SUBSCRIPTION_ID="$(az account show --query id --output tsv)"
TENANT_ID="$(az account show --query tenantId --output tsv)"
if [[ -z "$SUBSCRIPTION_ID" || -z "$TENANT_ID" ]]; then
  echo 'No active Azure subscription/tenant. Select the intended account before running.' >&2
  exit 1
fi

for group in "$CONTROL_RG" "$DRIVER_RG"; do
  az group show --subscription "$SUBSCRIPTION_ID" --name "$group" --query id --output tsv >/dev/null
done

if ! az identity show --subscription "$SUBSCRIPTION_ID" --resource-group "$CONTROL_RG" --name "$IDENTITY_NAME" --query id --output tsv >/dev/null 2>&1; then
  az identity create --subscription "$SUBSCRIPTION_ID" --resource-group "$CONTROL_RG" --name "$IDENTITY_NAME" --location "$LOCATION" --output none
fi

CLIENT_ID="$(az identity show --subscription "$SUBSCRIPTION_ID" --resource-group "$CONTROL_RG" --name "$IDENTITY_NAME" --query clientId --output tsv)"
PRINCIPAL_ID="$(az identity show --subscription "$SUBSCRIPTION_ID" --resource-group "$CONTROL_RG" --name "$IDENTITY_NAME" --query principalId --output tsv)"
if [[ -z "$CLIENT_ID" || -z "$PRINCIPAL_ID" ]]; then
  echo 'The dedicated managed identity is not fully provisioned.' >&2
  exit 1
fi

if ! az identity federated-credential show --subscription "$SUBSCRIPTION_ID" --resource-group "$CONTROL_RG" --identity-name "$IDENTITY_NAME" --name "$FEDERATION_NAME" --query name --output tsv >/dev/null 2>&1; then
  az identity federated-credential create \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$CONTROL_RG" \
    --identity-name "$IDENTITY_NAME" \
    --name "$FEDERATION_NAME" \
    --issuer 'https://token.actions.githubusercontent.com' \
    --subject "$OIDC_SUBJECT" \
    --audiences 'api://AzureADTokenExchange' \
    --output none
fi

SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${DRIVER_RG}"
ASSIGNMENT_COUNT="$(az role assignment list --subscription "$SUBSCRIPTION_ID" --assignee "$PRINCIPAL_ID" --scope "$SCOPE" --role Reader --query 'length(@)' --output tsv)"
if [[ "$ASSIGNMENT_COUNT" == '0' ]]; then
  az role assignment create \
    --subscription "$SUBSCRIPTION_ID" \
    --assignee-object-id "$PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role Reader \
    --scope "$SCOPE" \
    --output none
fi

printf '%s' "$CLIENT_ID" | gh secret set AZURE_CLIENT_ID --repo "$REPO"
printf '%s' "$TENANT_ID" | gh secret set AZURE_TENANT_ID --repo "$REPO"
printf '%s' "$SUBSCRIPTION_ID" | gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO"

echo 'OIDC_BOOTSTRAP_CONFIGURED: test the manual Azure inventory workflow in GitHub Actions.'
echo 'No virtual machines were started or modified.'
