#!/usr/bin/env bash
# bootstrap.sh — Initial setup for Fabric Access Platform
#
# Creates the Entra ID app registration, grants API permissions, and
# configures the Fabric Admin Portal prerequisites.
#
# Prerequisites:
#   - Azure CLI authenticated with Global Admin or Application Admin
#   - Fabric Admin role for the executing user
#
# Usage:
#   ./scripts/bootstrap.sh [--tenant-id <tid>] [--subscription-id <sid>]

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_NAME="${APP_NAME:-fabric-access-platform}"
REDIRECT_URI="http://localhost"

TENANT_ID="${1:---tenant-id}"
SUBSCRIPTION_ID=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tenant-id) TENANT_ID="$2"; shift 2 ;;
        --subscription-id) SUBSCRIPTION_ID="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "=================================================="
echo "  Fabric Access Platform — Bootstrap"
echo "=================================================="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Create App Registration
# ---------------------------------------------------------------------------
echo "[1/6] Creating Entra ID app registration: ${APP_NAME}"

APP_ID=$(az ad app create \
    --display-name "${APP_NAME}" \
    --sign-in-audience "AzureADMyOrg" \
    --web-redirect-uris "${REDIRECT_URI}" \
    --query appId -o tsv 2>/dev/null)

echo "       App ID: ${APP_ID}"

# Create service principal
SP_OBJECT_ID=$(az ad sp create --id "${APP_ID}" --query id -o tsv 2>/dev/null || \
    az ad sp show --id "${APP_ID}" --query id -o tsv)

echo "       SP Object ID: ${SP_OBJECT_ID}"

# ---------------------------------------------------------------------------
# Step 2: Grant API Permissions
# ---------------------------------------------------------------------------
echo ""
echo "[2/6] Granting API permissions"

# Power BI Service API permissions (required for workspace + item management)
PBI_API_ID="00000009-0000-0000-c000-000000000000"

# Tenant.ReadWrite.All — Manage tenant settings
az ad app permission add --id "${APP_ID}" \
    --api "${PBI_API_ID}" \
    --api-permissions "4ae1bf56-f562-4747-b7bc-2fa0874ed46f=Role" \
    2>/dev/null || true

# Workspace.ReadWrite.All — Manage workspaces
az ad app permission add --id "${APP_ID}" \
    --api "${PBI_API_ID}" \
    --api-permissions "a65a6bd9-0978-46d6-a261-36b3e6fdd32e=Role" \
    2>/dev/null || true

# Item.ReadWrite.All — Manage items
az ad app permission add --id "${APP_ID}" \
    --api "${PBI_API_ID}" \
    --api-permissions "7f33e027-4039-419b-a540-b53d3b0b3906=Role" \
    2>/dev/null || true

# Item.Execute.All — Execute items (refresh, pipeline runs)
az ad app permission add --id "${APP_ID}" \
    --api "${PBI_API_ID}" \
    --api-permissions "3c05294f-7a3f-461c-80fd-f52bab0e24e2=Role" \
    2>/dev/null || true

# Microsoft Graph permissions (for group membership monitoring)
GRAPH_API_ID="00000003-0000-0000-c000-000000000000"

# GroupMember.Read.All — Read group memberships
az ad app permission add --id "${APP_ID}" \
    --api "${GRAPH_API_ID}" \
    --api-permissions "98830695-27a2-44f7-8c18-0c3ebc9698f6=Role" \
    2>/dev/null || true

# User.Read.All — Read user profiles
az ad app permission add --id "${APP_ID}" \
    --api "${GRAPH_API_ID}" \
    --api-permissions "df021288-bdef-4463-88db-98f22de89214=Role" \
    2>/dev/null || true

echo "       Permissions added. Admin consent required."

# ---------------------------------------------------------------------------
# Step 3: Grant Admin Consent
# ---------------------------------------------------------------------------
echo ""
echo "[3/6] Granting admin consent"

az ad app permission admin-consent --id "${APP_ID}" 2>/dev/null || \
    echo "       WARNING: Admin consent may require manual approval in Azure Portal"

# ---------------------------------------------------------------------------
# Step 4: Create Client Secret
# ---------------------------------------------------------------------------
echo ""
echo "[4/6] Creating client secret"

SECRET=$(az ad app credential reset \
    --id "${APP_ID}" \
    --display-name "fabric-access-platform-secret" \
    --years 1 \
    --query password -o tsv)

echo "       Secret created (expires in 1 year)"

# ---------------------------------------------------------------------------
# Step 5: Create Resource Group + Function App Infrastructure
# ---------------------------------------------------------------------------
echo ""
echo "[5/6] Setting up Azure infrastructure"

RG_NAME="rg-fabric-access-platform"
LOCATION="eastus"
FUNC_APP_NAME="func-fabric-access-$(openssl rand -hex 4)"
STORAGE_NAME="stfabricaccess$(openssl rand -hex 4)"

if [[ -n "${SUBSCRIPTION_ID}" ]]; then
    az account set --subscription "${SUBSCRIPTION_ID}"
fi

az group create --name "${RG_NAME}" --location "${LOCATION}" -o none

az storage account create \
    --name "${STORAGE_NAME}" \
    --resource-group "${RG_NAME}" \
    --location "${LOCATION}" \
    --sku Standard_LRS \
    --min-tls-version TLS1_2 \
    -o none

az functionapp create \
    --name "${FUNC_APP_NAME}" \
    --resource-group "${RG_NAME}" \
    --storage-account "${STORAGE_NAME}" \
    --consumption-plan-location "${LOCATION}" \
    --runtime python \
    --runtime-version 3.11 \
    --functions-version 4 \
    --os-type Linux \
    -o none

# Set function app configuration
az functionapp config appsettings set \
    --name "${FUNC_APP_NAME}" \
    --resource-group "${RG_NAME}" \
    --settings \
        "AZURE_TENANT_ID=${TENANT_ID}" \
        "FABRIC_CLIENT_ID=${APP_ID}" \
        "FABRIC_CLIENT_SECRET=${SECRET}" \
    -o none

echo "       Function App: ${FUNC_APP_NAME}"
echo "       Storage:      ${STORAGE_NAME}"

# ---------------------------------------------------------------------------
# Step 6: Output Summary
# ---------------------------------------------------------------------------
echo ""
echo "=================================================="
echo "  Bootstrap Complete"
echo "=================================================="
echo ""
echo "  Tenant ID:        ${TENANT_ID}"
echo "  App ID:           ${APP_ID}"
echo "  SP Object ID:     ${SP_OBJECT_ID}"
echo "  Client Secret:    ${SECRET}"
echo "  Function App:     ${FUNC_APP_NAME}"
echo ""
echo "  IMPORTANT — Manual steps required:"
echo ""
echo "  1. In Fabric Admin Portal, enable:"
echo "     - 'Service principals can use Fabric APIs'"
echo "     - Add the SPN to allowed security group"
echo ""
echo "  2. Add the SPN to target workspaces:"
echo "     - As Contributor (for item management)"
echo "     - Or Admin (for full permission management)"
echo ""
echo "  3. Store credentials in GitHub Secrets:"
echo "     - AZURE_TENANT_ID"
echo "     - FABRIC_CLIENT_ID"
echo "     - FABRIC_CLIENT_SECRET"
echo ""
echo "  4. Initialize Fabric token for the SPN:"
echo "     curl -X GET 'https://api.fabric.microsoft.com/v1/workspaces' \\"
echo "       -H 'Authorization: Bearer <token>'"
echo ""
