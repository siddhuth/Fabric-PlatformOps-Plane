# Operations Runbook

Day-to-day operational procedures for the Fabric Access Platform.

## Table of Contents

- [Adding a New Access Package](#adding-a-new-access-package)
- [Onboarding a New Workspace](#onboarding-a-new-workspace)
- [Emergency Access Override](#emergency-access-override)
- [Handling Drift Alerts](#handling-drift-alerts)
- [Rotating the Service Principal Secret](#rotating-the-service-principal-secret)
- [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Adding a New Access Package

When a new persona needs access to Fabric resources, create a new YAML definition.

**Step 1: Create the YAML file**

Copy an existing definition as a template:

```bash
cp access-packages/definitions/data-engineer.yaml \
   access-packages/definitions/ml-engineer.yaml
```

Edit the new file, updating:
- `package.name` — Unique kebab-case identifier
- `package.entra_group` — Must start with `sg-fabric-` and be unique across all packages
- `grants.workspace.role` — Appropriate role level
- `grants.items` — Items this persona needs access to
- `grants.compute` — SQL grants and OneLake security
- `metadata` — Owner, domain, sensitivity, review date

**Step 2: Validate locally**

```bash
python scripts/validate_packages.py
```

Fix any errors before proceeding.

**Step 3: Create a PR**

```bash
git checkout -b add-ml-engineer-package
git add access-packages/definitions/ml-engineer.yaml
git commit -m "Add ML engineer access package for sales workspace"
git push origin add-ml-engineer-package
```

The `validate-access-packages` workflow will run automatically.

**Step 4: After merge, Terraform creates the Entra security group**

Run Terraform apply (or let the CI pipeline handle it):

```bash
cd terraform/environments/dev
terraform plan -var-file=terraform.tfvars
terraform apply
```

**Step 5: Configure the Entra Access Package in Azure Portal**

Navigate to Entra ID Governance and create an Access Package that:
- Targets the new security group (`sg-fabric-ml-sales`)
- Uses the approval policy specified in the YAML
- Sets the expiration matching `expiration_days`

This step is currently manual. A future enhancement will automate it via the Microsoft Graph API.

---

## Onboarding a New Workspace

**Step 1: Add the workspace to the environment tfvars**

```hcl
# terraform/environments/dev/terraform.tfvars
workspaces = {
  # ... existing workspaces ...

  finance-lakehouse = {
    display_name = "Finance Lakehouse - Dev"
    description  = "Finance domain lakehouse and analytics."
    git_config = {
      provider_type = "GitHub"
      owner         = "your-org"
      repository    = "fabric-finance"
      branch        = "dev"
      directory     = "/fabric"
    }
  }
}
```

**Step 2: Create access packages for the new workspace**

Create YAML definitions for each persona that needs access (data-engineer-finance.yaml, analytics-finance.yaml, etc.).

**Step 3: Set environment variables for the Function App**

Add the new workspace ID as an environment variable:

```bash
az functionapp config appsettings set \
  --name func-fabric-access-xxxx \
  --resource-group rg-fabric-access-platform \
  --settings "WORKSPACE_FINANCE_ID=<workspace-guid>"
```

**Step 4: Apply Terraform and deploy functions**

```bash
cd terraform/environments/dev
terraform apply -var-file=terraform.tfvars
```

---

## Emergency Access Override

For time-critical access needs that cannot wait for the normal approval flow.

**Step 1: Document the justification**

Record why emergency access is needed and the expected duration.

**Step 2: Manually trigger the provisioning function**

```bash
curl -X POST "https://func-fabric-access-xxxx.azurewebsites.net/api/provision" \
  -H "Content-Type: application/json" \
  -H "x-functions-key: <function-key>" \
  -d '{
    "group_name": "sg-fabric-de-sales",
    "user_id": "<user-object-id>",
    "user_email": "user@contoso.com",
    "action": "add"
  }'
```

**Step 3: Set a calendar reminder to revoke**

Emergency access must be time-boxed. After the emergency window:

```bash
curl -X POST "https://func-fabric-access-xxxx.azurewebsites.net/api/provision" \
  -H "Content-Type: application/json" \
  -H "x-functions-key: <function-key>" \
  -d '{
    "group_name": "sg-fabric-de-sales",
    "user_id": "<user-object-id>",
    "user_email": "user@contoso.com",
    "action": "remove"
  }'
```

**Step 4: File a post-incident review**

Document the emergency access event and determine if the access package framework needs updating to prevent future emergencies.

---

## Handling Drift Alerts

The drift detector runs daily at 6 AM UTC. When drift is detected:

**Step 1: Review the drift report**

Check Azure Monitor logs or trigger a manual scan:

```bash
curl -X POST "https://func-fabric-access-xxxx.azurewebsites.net/api/drift-scan" \
  -H "x-functions-key: <function-key>"
```

**Step 2: Classify the findings**

| Category | Action |
|----------|--------|
| **Shadow access** (user has access not in any package) | Investigate. Either add them to the correct package or revoke the access. |
| **Over-provisioned** (actual > declared) | Reduce permissions to match the YAML. This is a security finding. |
| **Under-provisioned** (actual < declared) | Re-run the provisioning function for the affected user/group. |

**Step 3: Remediate**

For over-provisioned access, the fastest remediation is to update the workspace role or item permissions manually in the Fabric portal, then verify the drift detector shows green on next run.

For persistent drift caused by manual portal changes, consider whether the YAML definitions need updating to reflect legitimate operational needs.

---

## Rotating the Service Principal Secret

Secrets expire annually. Rotate before expiry.

**Step 1: Generate a new secret**

```bash
NEW_SECRET=$(az ad app credential reset \
  --id <app-id> \
  --display-name "fabric-access-platform-secret-v2" \
  --years 1 \
  --query password -o tsv)
```

**Step 2: Update Azure Function App settings**

```bash
az functionapp config appsettings set \
  --name func-fabric-access-xxxx \
  --resource-group rg-fabric-access-platform \
  --settings "FABRIC_CLIENT_SECRET=${NEW_SECRET}"
```

**Step 3: Update GitHub Secrets**

Update `FABRIC_CLIENT_SECRET` in the repository's GitHub Secrets.

**Step 4: Delete the old secret**

```bash
az ad app credential list --id <app-id>
az ad app credential delete --id <app-id> --key-id <old-key-id>
```

---

## Troubleshooting Common Issues

### "The calling principal has no sufficient permissions over the target capacity"

The SPN needs Capacity Contributor role on the Fabric capacity. Assign via Azure Portal on the capacity resource's IAM blade.

### "Service principal token not found" or "File not found" errors

New SPNs must bootstrap their Fabric token by making an initial API call:

```bash
TOKEN=$(az account get-access-token \
  --resource "https://api.fabric.microsoft.com" \
  --query accessToken -o tsv)

curl -X GET "https://api.fabric.microsoft.com/v1/workspaces" \
  -H "Authorization: Bearer ${TOKEN}"
```

### Item sharing returns 404

The item may not exist in the workspace yet (e.g., the mirrored database hasn't been created). Verify item existence first:

```bash
curl -X GET "https://api.fabric.microsoft.com/v1/workspaces/{wsId}/items" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.value[] | {displayName, type, id}'
```

### SQL grants fail with "Cannot find the user"

The Entra principal must exist in the SQL database. The provisioning function runs `CREATE USER FROM EXTERNAL PROVIDER` idempotently, but if the SQL endpoint is new, the user creation may need a few seconds after workspace role assignment to propagate.

### Terraform plan shows unwanted changes to group members

The `azuread_group` resource has `ignore_changes = [members]` set because group membership is managed by Entra Access Packages, not Terraform. If you see member changes in the plan, verify the lifecycle block is present.

### Permission changes take up to 2 hours to propagate

This is by design in Fabric. When a user's permission is granted or revoked, it can take up to 2 hours for signed-in users to see the change. Signing out and back in applies changes immediately.
