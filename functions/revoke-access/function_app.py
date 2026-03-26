"""
revoke-access — Azure Function triggered when a user is removed from
an access package security group (expiration, manual removal, or
recertification failure).

Mirrors the provision-access function but executes revocation:
  1. Removes workspace role
  2. Logs item permission revocations for manual follow-up
  3. Executes T-SQL REVOKE statements
  4. Logs audit events

Note: Item-level permission revocation via API is limited in Fabric.
The function logs these for platform team manual action via the
control plane UI.
"""

import os
import json
import logging
import azure.functions as func
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from fabric_client import FabricClient, ProvisioningResult
from sql_grants import revoke_sql_access

logger = logging.getLogger(__name__)

ACCESS_PACKAGES_DIR = os.environ.get(
    "ACCESS_PACKAGES_DIR",
    os.path.join(os.path.dirname(__file__), '..', '..', 'access-packages', 'definitions')
)

app = func.FunctionApp()


@app.function_name("revoke-access")
@app.route(route="revoke", methods=["POST"])
async def revoke_access(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP-triggered function for revoking access.

    Expected payload:
    {
        "group_name": "sg-fabric-de-sales",
        "user_id": "<entra-user-object-id>",
        "user_email": "user@contoso.com",
        "reason": "expiration" | "manual" | "recertification"
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    group_name = body.get("group_name")
    user_id = body.get("user_id")
    user_email = body.get("user_email", "unknown")
    reason = body.get("reason", "manual")

    if not group_name or not user_id:
        return func.HttpResponse("Missing required fields", status_code=400)

    logger.info(f"Revocation request: user {user_email}, group {group_name}, reason: {reason}")

    # Load matching access package
    package = _load_package_for_group(group_name)
    if not package:
        return func.HttpResponse(f"No access package for group: {group_name}", status_code=404)

    client = FabricClient.from_environment()
    results = []
    grants = package.get("grants", {})

    # --- Revoke workspace role ---
    ws_config = grants.get("workspace", {})
    workspace_id = _resolve_env(ws_config.get("id", ""))
    if workspace_id:
        result = client.remove_workspace_role(workspace_id, user_id)
        results.append(result)
        logger.info(f"Workspace role removal: {result.detail}")

    # --- Log item permission revocations ---
    for item_config in grants.get("items", []):
        item_name = item_config.get("name", "unknown")
        results.append(ProvisioningResult(
            layer="item", target=item_name,
            action="revoke_item_logged", success=True,
            detail=f"Item permission revocation queued for manual review ({item_name})",
            principal_id=user_id,
        ))
        logger.warning(f"MANUAL ACTION REQUIRED: Revoke item permissions for "
                       f"{user_email} on {item_name}")

    # --- Revoke SQL grants ---
    sql_config = grants.get("compute", {}).get("sql_endpoint", {})
    if sql_config.get("grants") or sql_config.get("deny"):
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
            results.append(ProvisioningResult(
                layer="compute", target="sql_endpoint",
                action="sql_revoke", success=False,
                detail=str(e), principal_id=user_id,
            ))

    # Build audit entry
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "revoke",
        "reason": reason,
        "user": user_email,
        "group": group_name,
        "package": package.get("package", {}).get("name", "unknown"),
        "results_summary": {
            "total": len(results),
            "succeeded": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
        },
    }
    logger.info(f"Revocation audit: {json.dumps(audit_entry)}")

    all_success = all(r.success for r in results)
    return func.HttpResponse(
        json.dumps({
            "status": "complete" if all_success else "partial",
            "results": [{"layer": r.layer, "target": r.target, "success": r.success, "detail": r.detail} for r in results],
            "audit": audit_entry,
        }),
        status_code=200 if all_success else 207,
        mimetype="application/json",
    )


def _load_package_for_group(group_name):
    import yaml
    if not os.path.isdir(ACCESS_PACKAGES_DIR):
        return None
    for filename in os.listdir(ACCESS_PACKAGES_DIR):
        if not filename.endswith(".yaml"):
            continue
        with open(os.path.join(ACCESS_PACKAGES_DIR, filename)) as f:
            pkg = yaml.safe_load(f)
        if pkg and pkg.get("package", {}).get("entra_group") == group_name:
            return pkg
    return None


def _resolve_env(ref):
    if ref.startswith("${") and ref.endswith("}"):
        return os.environ.get(ref[2:-1], "")
    return ref
