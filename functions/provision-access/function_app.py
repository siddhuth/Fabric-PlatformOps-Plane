"""
provision-access — Azure Function triggered by Entra ID group membership changes.

When a user is added to an access package security group (via Entra ID
Governance approval), this function:

  1. Identifies which access package YAML maps to the changed group
  2. Dispatches provisioning to the appropriate platform providers
     (Fabric, Databricks, or both) via the provider registry
  3. Each provider handles its own layers (workspace roles, item sharing,
     UC grants, workspace ACLs, SQL grants, entitlements)
  4. Logs all provisioning events to Azure Monitor / Log Analytics

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
from provider_registry import get_all_providers, ProvisioningResult

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

    # Get all platform providers for this package
    providers = get_all_providers(package)

    # Execute provisioning/revocation across all platforms
    results: list[ProvisioningResult] = []
    for provider in providers:
        logger.info(f"Dispatching {action} to {provider.platform_name} provider")
        try:
            if action == "add":
                results.extend(provider.provision(package, user_id, user_email))
            elif action == "remove":
                results.extend(provider.revoke(package, user_id, user_email))
        except Exception as e:
            logger.error(f"Provider {provider.platform_name} failed: {e}")
            results.append(ProvisioningResult(
                platform=provider.platform_name, layer="dispatch",
                target="provider", action=action, success=False,
                detail=str(e), principal_id=user_id,
            ))

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
                    "platform": r.platform,
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


def _build_audit_entry(action: str, user_email: str, group_name: str,
                       package: dict, results: list[ProvisioningResult]) -> dict:
    """Build a structured audit log entry for Log Analytics."""
    # Group results by platform
    platforms_involved = list({r.platform for r in results})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user": user_email,
        "group": group_name,
        "package": package.get("package", {}).get("name", "unknown"),
        "version": package.get("package", {}).get("version", "unknown"),
        "platforms": platforms_involved,
        "results_summary": {
            "total": len(results),
            "succeeded": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
        },
        "results_detail": [
            {"platform": r.platform, "layer": r.layer, "target": r.target,
             "success": r.success, "detail": r.detail}
            for r in results
        ],
    }
