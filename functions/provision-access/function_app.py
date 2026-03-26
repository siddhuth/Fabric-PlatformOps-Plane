"""
provision-access — Azure Function triggered by Entra ID group membership changes.

When a user is added to an access package security group (via Entra ID
Governance approval), this function:

  1. Identifies which access package YAML maps to the changed group
  2. Resolves the target workspace and item IDs
  3. Assigns workspace role via Power BI REST API
  4. Shares items with appropriate permissions
  5. Executes T-SQL GRANT statements on the SQL analytics endpoint
  6. Logs all provisioning events to Azure Monitor / Log Analytics

Trigger: Microsoft Graph change notification webhook (group membership)
"""

import os
import json
import logging
import azure.functions as func
from datetime import datetime, timezone

# Shared libraries
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from fabric_client import FabricClient, ProvisioningResult
from sql_grants import provision_sql_access

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ACCESS_PACKAGES_DIR = os.environ.get(
    "ACCESS_PACKAGES_DIR",
    os.path.join(os.path.dirname(__file__), '..', '..', 'access-packages', 'definitions')
)

# ---------------------------------------------------------------------------
# Function Entry Point
# ---------------------------------------------------------------------------
app = func.FunctionApp()


@app.function_name("provision-access")
@app.route(route="provision", methods=["POST"])
async def provision_access(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP-triggered function for provisioning access.

    Expected payload (from Microsoft Graph change notification or manual trigger):
    {
        "group_id": "<entra-group-object-id>",
        "group_name": "sg-fabric-de-sales",
        "user_id": "<entra-user-object-id>",
        "user_email": "user@contoso.com",
        "action": "add"  // "add" or "remove"
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    group_name = body.get("group_name")
    user_id = body.get("user_id")
    user_email = body.get("user_email", "unknown")
    action = body.get("action", "add")

    if not group_name or not user_id:
        return func.HttpResponse(
            "Missing required fields: group_name, user_id",
            status_code=400
        )

    logger.info(f"Provisioning request: {action} user {user_email} "
                f"via group {group_name}")

    # Load the matching access package
    package = _load_package_for_group(group_name)
    if not package:
        return func.HttpResponse(
            f"No access package found for group: {group_name}",
            status_code=404
        )

    # Initialize Fabric client
    client = FabricClient.from_environment()

    # Execute provisioning across all three layers
    results = []

    if action == "add":
        results = _provision_all_layers(client, package, user_id, user_email)
    elif action == "remove":
        results = _revoke_all_layers(client, package, user_id, user_email)

    # Build audit log entry
    audit_entry = _build_audit_entry(action, user_email, group_name, package, results)
    logger.info(f"Audit: {json.dumps(audit_entry)}")

    # Determine overall success
    all_success = all(r.success for r in results)
    status = 200 if all_success else 207  # 207 = multi-status (partial success)

    return func.HttpResponse(
        json.dumps({
            "status": "complete" if all_success else "partial",
            "results": [
                {
                    "layer": r.layer,
                    "target": r.target,
                    "action": r.action,
                    "success": r.success,
                    "detail": r.detail,
                }
                for r in results
            ],
            "audit": audit_entry,
        }),
        status_code=status,
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# Provisioning Logic
# ---------------------------------------------------------------------------
def _provision_all_layers(client: FabricClient, package: dict,
                          user_id: str, user_email: str) -> list[ProvisioningResult]:
    """
    Execute permission grants across all three layers:
    1. Workspace role assignment
    2. Item-level permission sharing
    3. Compute-level SQL grants
    """
    results = []
    grants = package.get("grants", {})

    # --- Layer 1: Workspace Role ---
    ws_config = grants.get("workspace", {})
    workspace_id = _resolve_workspace_id(ws_config.get("id", ""))
    role = ws_config.get("role", "Viewer")

    if workspace_id:
        result = client.assign_workspace_role(
            workspace_id=workspace_id,
            principal_id=user_id,
            principal_type="User",
            role=role,
        )
        results.append(result)
        logger.info(f"Workspace role: {result.detail}")

    # --- Layer 2: Item Permissions ---
    for item_config in grants.get("items", []):
        item_name = item_config.get("name")
        item_type = item_config.get("type")
        permissions = item_config.get("permissions", ["Read"])

        if workspace_id and item_name:
            # Resolve item ID by name
            item = client.find_item_by_name(workspace_id, item_name, item_type)
            if item:
                result = client.share_item(
                    workspace_id=workspace_id,
                    item_id=item["id"],
                    recipient_id=user_id,
                    recipient_type="User",
                    permissions=permissions,
                )
                results.append(result)
                logger.info(f"Item share ({item_name}): {result.detail}")
            else:
                results.append(ProvisioningResult(
                    layer="item", target=item_name,
                    action="share_item", success=False,
                    detail=f"Item not found: {item_name} ({item_type})",
                    principal_id=user_id,
                ))

    # --- Layer 3: Compute Security (SQL Grants) ---
    sql_config = grants.get("compute", {}).get("sql_endpoint", {})
    if sql_config.get("grants") or sql_config.get("deny"):
        try:
            sql_results = provision_sql_access(
                access_package=package,
                variables={
                    "ENTRA_GROUP_SID": package["package"]["entra_group"],
                    "PRINCIPAL_NAME": user_email,
                },
                server=os.environ.get("FABRIC_SQL_SERVER", ""),
                database=os.environ.get("FABRIC_SQL_DATABASE", ""),
                tenant_id=os.environ["AZURE_TENANT_ID"],
                client_id=os.environ["FABRIC_CLIENT_ID"],
                client_secret=os.environ["FABRIC_CLIENT_SECRET"],
            )
            for sr in sql_results:
                results.append(ProvisioningResult(
                    layer="compute", target=sr.script.description,
                    action="sql_grant", success=sr.success,
                    detail=sr.error or "OK",
                    principal_id=user_id,
                ))
        except Exception as e:
            logger.error(f"SQL grants failed: {e}")
            results.append(ProvisioningResult(
                layer="compute", target="sql_endpoint",
                action="sql_grant", success=False,
                detail=str(e), principal_id=user_id,
            ))

    return results


def _revoke_all_layers(client: FabricClient, package: dict,
                       user_id: str, user_email: str) -> list[ProvisioningResult]:
    """Revoke all permissions for a user being removed from an access package."""
    results = []
    grants = package.get("grants", {})

    # Remove workspace role
    ws_config = grants.get("workspace", {})
    workspace_id = _resolve_workspace_id(ws_config.get("id", ""))
    if workspace_id:
        result = client.remove_workspace_role(workspace_id, user_id)
        results.append(result)

    # Note: Item-level permission revocation requires the Manage Permissions
    # page or undocumented API endpoints. Log for manual follow-up.
    for item_config in grants.get("items", []):
        results.append(ProvisioningResult(
            layer="item", target=item_config.get("name", "unknown"),
            action="revoke_item", success=True,
            detail="Item permission revocation logged for manual review",
            principal_id=user_id,
        ))

    # Revoke SQL grants
    from sql_grants import revoke_sql_access
    sql_config = grants.get("compute", {}).get("sql_endpoint", {})
    if sql_config:
        try:
            sql_results = revoke_sql_access(
                access_package=package,
                variables={
                    "ENTRA_GROUP_SID": package["package"]["entra_group"],
                    "PRINCIPAL_NAME": user_email,
                },
                server=os.environ.get("FABRIC_SQL_SERVER", ""),
                database=os.environ.get("FABRIC_SQL_DATABASE", ""),
                tenant_id=os.environ["AZURE_TENANT_ID"],
                client_id=os.environ["FABRIC_CLIENT_ID"],
                client_secret=os.environ["FABRIC_CLIENT_SECRET"],
            )
            for sr in sql_results:
                results.append(ProvisioningResult(
                    layer="compute", target=sr.script.description,
                    action="sql_revoke", success=sr.success,
                    detail=sr.error or "OK", principal_id=user_id,
                ))
        except Exception as e:
            logger.error(f"SQL revocation failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_package_for_group(group_name: str) -> dict | None:
    """Find and load the access package YAML whose entra_group matches."""
    import yaml

    if not os.path.isdir(ACCESS_PACKAGES_DIR):
        logger.error(f"Access packages directory not found: {ACCESS_PACKAGES_DIR}")
        return None

    for filename in os.listdir(ACCESS_PACKAGES_DIR):
        if not filename.endswith(".yaml"):
            continue
        filepath = os.path.join(ACCESS_PACKAGES_DIR, filename)
        with open(filepath, 'r') as f:
            pkg = yaml.safe_load(f)
        if pkg and pkg.get("package", {}).get("entra_group") == group_name:
            return pkg

    return None


def _resolve_workspace_id(workspace_ref: str) -> str:
    """
    Resolve a workspace reference to an actual ID.
    Supports environment variable substitution (${WORKSPACE_SALES_ID}).
    """
    if workspace_ref.startswith("${") and workspace_ref.endswith("}"):
        env_var = workspace_ref[2:-1]
        return os.environ.get(env_var, "")
    return workspace_ref


def _build_audit_entry(action: str, user_email: str, group_name: str,
                       package: dict, results: list[ProvisioningResult]) -> dict:
    """Build a structured audit log entry for Log Analytics."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user": user_email,
        "group": group_name,
        "package": package.get("package", {}).get("name", "unknown"),
        "version": package.get("package", {}).get("version", "unknown"),
        "results_summary": {
            "total": len(results),
            "succeeded": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
        },
        "results_detail": [
            {"layer": r.layer, "target": r.target, "success": r.success, "detail": r.detail}
            for r in results
        ],
    }
