#!/usr/bin/env bash
# K2401 / Owner-only, idempotent Microsoft Entra model-inference RBAC repair.
# Does not create Azure services, start any Container Apps jobs or start any VM.
# Required because a subscription Contributor role grants no Azure AI data-plane access.
set -euo pipefail

SUB='0ac7a514-32b3-47bf-bf89-e17906b1cc86'
TENANT='779623db-ec2e-495b-9828-85d42baa77ee'
IDENTITY_RG='rg-chatgpt-azure'
IDENTITY_NAME='k2401-github-oidc'
EXPECTED_CLIENT='50a5c260-15a0-4aa0-9e02-5f0ad5c23df9'
EXPECTED_PRINCIPAL='32e6befe-9e61-4470-9758-ed89a907c1f4'
AI_SCOPE="/subscriptions/$SUB/resourceGroups/NetworkWatcherRG/providers/Microsoft.CognitiveServices/accounts/andreplaja-6488-resource"
ROLE='Cognitive Services OpenAI User'

az account set --subscription "$SUB"
[[ "$(az account show --query tenantId -o tsv)" == "$TENANT" ]] || {
  echo 'TENANT_MISMATCH: refused to grant role'; exit 2;
}
CLIENT="$(az identity show -g "$IDENTITY_RG" -n "$IDENTITY_NAME" --query clientId -o tsv)"
PRINCIPAL="$(az identity show -g "$IDENTITY_RG" -n "$IDENTITY_NAME" --query principalId -o tsv)"
[[ "$CLIENT" == "$EXPECTED_CLIENT" && "$PRINCIPAL" == "$EXPECTED_PRINCIPAL" ]] || {
  echo 'IDENTITY_MISMATCH: refused to grant role'; exit 2;
}
az cognitiveservices account show -g NetworkWatcherRG -n andreplaja-6488-resource --query id -o tsv |
  grep -Fx "$AI_SCOPE" >/dev/null
az cognitiveservices account deployment show -g NetworkWatcherRG -n andreplaja-6488-resource \
  --deployment-name k2401-gpt41mini --query properties.provisioningState -o tsv |
  grep -Fx 'Succeeded' >/dev/null

COUNT="$(az role assignment list --assignee "$PRINCIPAL" --scope "$AI_SCOPE" --role "$ROLE" --query 'length(@)' -o tsv)"
if [[ "$COUNT" == '0' ]]; then
  az role assignment create --assignee-object-id "$PRINCIPAL" \
    --assignee-principal-type ServicePrincipal --role "$ROLE" --scope "$AI_SCOPE" -o none
  echo 'AZURE_AI_INFERENCE_RBAC_CREATED=PASS'
else
  echo 'AZURE_AI_INFERENCE_RBAC_ALREADY_PRESENT=PASS'
fi
COUNT="$(az role assignment list --assignee "$PRINCIPAL" --scope "$AI_SCOPE" --role "$ROLE" --query 'length(@)' -o tsv)"
[[ "$COUNT" =~ ^[1-9][0-9]*$ ]] || { echo 'AZURE_AI_RBAC_VERIFICATION_FAILED'; exit 3; }
echo 'AZURE_AI_INFERENCE_RBAC=PASS'
echo 'No VM or Azure AI job was started. Allow up to 5 minutes for Entra role propagation.'
