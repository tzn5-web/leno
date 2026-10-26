#!/usr/bin/env bash
# K2401: ONE-TIME subscription-Owner bootstrap of a genuine Azure AI diagnostic job.
# Reuses existing Container Apps environment & Foundry account. Creates a manual
# scale-to-zero job (no idle CPU), one narrowly scoped managed identity and one
# standard pay-per-token model deployment. Never starts the Windows VM.
set -euo pipefail

SUB=0ac7a514-32b3-47bf-bf89-e17906b1cc86
TENANT=779623db-ec2e-495b-9828-85d42baa77ee
RG=rg-chatgpt-azure
ENV=chatgpt-azure-control-env
JOB=k2401-ai-agent
MI=k2401-ai-agent-reader
FOUNDRY_RG=NetworkWatcherRG
FOUNDRY=andreplaja-6488-resource
DEPLOYMENT=k2401-gpt41mini
GITHUB_PRINCIPAL=32e6befe-9e61-4470-9758-ed89a907c1f4
VM_SCOPE="/subscriptions/$SUB/resourceGroups/rg-phaser360-driverlab/providers/Microsoft.Compute/virtualMachines/int34d2-lab"
AI_SCOPE="/subscriptions/$SUB/resourceGroups/$FOUNDRY_RG/providers/Microsoft.CognitiveServices/accounts/$FOUNDRY"
PINNED_SHA=2be05edb02bd10a58f0ff5ef81f2ee5744696b0d
SCRIPT_URL="https://raw.githubusercontent.com/tzn5-web/leno/$PINNED_SHA/projects/k2401-evo-launcher/agent/azure_entry.py"

az account set --subscription "$SUB"
[[ "$(az account show --query tenantId -o tsv)" == "$TENANT" ]] || { echo 'AZURE_AGENT_TENANT_MISMATCH'; exit 2; }
az containerapp env show -g "$RG" -n "$ENV" --query id -o tsv >/dev/null
az cognitiveservices account show -g "$FOUNDRY_RG" -n "$FOUNDRY" --query id -o tsv >/dev/null
curl -fsS --max-time 20 "$SCRIPT_URL" -o /tmp/k2401-azure-entry.py
python3 -m py_compile /tmp/k2401-azure-entry.py
echo 'AZURE_AGENT_SOURCE_VALIDATED=PASS'

# Dedicated read-only identity; never reuse the VM Contributor identity for this agent.
if ! az identity show -g "$RG" -n "$MI" -o none >/dev/null 2>&1; then
  az identity create -g "$RG" -n "$MI" -l swedencentral -o none
fi
IDENTITY_ID="$(az identity show -g "$RG" -n "$MI" --query id -o tsv)"
CLIENT_ID="$(az identity show -g "$RG" -n "$MI" --query clientId -o tsv)"
PRINCIPAL_ID="$(az identity show -g "$RG" -n "$MI" --query principalId -o tsv)"
if [[ -z "$IDENTITY_ID" || -z "$CLIENT_ID" || -z "$PRINCIPAL_ID" ]]; then
  echo 'AZURE_AGENT_IDENTITY_INVALID'; exit 2
fi

ensure_role() {
  local object="$1" scope="$2" role="$3" count
  count="$(az role assignment list --assignee "$object" --scope "$scope" --role "$role" --query 'length(@)' -o tsv 2>/dev/null || echo 0)"
  if [[ "$count" == 0 ]]; then
    az role assignment create --assignee-object-id "$object" --assignee-principal-type ServicePrincipal \
      --scope "$scope" --role "$role" -o none
  fi
}
ensure_role "$PRINCIPAL_ID" "$VM_SCOPE" Reader
ensure_role "$PRINCIPAL_ID" "$AI_SCOPE" 'Cognitive Services OpenAI User'
echo 'AZURE_AGENT_RBAC=PASS'

# Standard (not provisioned) deployment: inference billed PER TOKEN; no PTU reservations.
# 1k TPM unit, max 450 output tokens per diagnosis. Reuse if already present.
if ! az cognitiveservices account deployment show -g "$FOUNDRY_RG" -n "$FOUNDRY" \
  --deployment-name "$DEPLOYMENT" --query name -o tsv >/dev/null 2>&1; then
  az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" \
    --deployment-name "$DEPLOYMENT" --model-name gpt-4.1-mini --model-version 2025-04-14 \
    --model-format OpenAI --sku-name Standard --sku-capacity 1 -o none
fi
echo 'AZURE_AGENT_MODEL=PASS'

# The source URL is pinned to an immutable Git commit. No GH PAT/API key in Azure.
# Azure CLI base image contains python3 and can use the attached managed identity.
PROGRAM="import urllib.request; exec(compile(urllib.request.urlopen('$SCRIPT_URL',timeout=20).read(), 'azure_entry.py','exec'))"
if ! az containerapp job show -g "$RG" -n "$JOB" --query name -o tsv >/dev/null 2>&1; then
  az containerapp job create -g "$RG" -n "$JOB" \
    --environment "$ENV" --trigger-type Manual \
    --replica-timeout 180 --replica-retry-limit 0 --replica-completion-count 1 --parallelism 1 \
    --image mcr.microsoft.com/azure-cli:2.74.0 --cpu 0.25 --memory 0.5Gi \
    --mi-user-assigned "$IDENTITY_ID" \
    --command python3 --args=-c "$PROGRAM" \
    --env-vars "AZURE_CLIENT_ID=$CLIENT_ID" "K2401_RUN_ID=40382269545" \
    -o none
fi
JOB_SCOPE="$(az containerapp job show -g "$RG" -n "$JOB" --query id -o tsv)"
[[ "$JOB_SCOPE" == "/subscriptions/$SUB/"* ]] || { echo 'AZURE_AGENT_JOB_SCOPE_INVALID'; exit 2; }
# GitHub OIDC may start this ONE job, but gets no blanket Contributor role.
ensure_role "$GITHUB_PRINCIPAL" "$JOB_SCOPE" 'Container Apps Jobs Operator'
echo 'AZURE_AGENT_JOB_CREATED=PASS'

# One bounded execution, CPU stops after completion; does NOT power on Windows VM.
az containerapp job start -g "$RG" -n "$JOB" -o json --query '{name:name,id:id}'
echo 'AZURE_AGENT_BOOTSTRAP=PASS'
echo 'AZURE_AGENT_MODEL_DEPLOYED=PASS'
echo 'AZURE_AGENT_MANUAL_JOB_STARTED=PASS'
