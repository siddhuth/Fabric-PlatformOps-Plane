"""
revoke-access — Azure Function triggered when a user is removed from
an access package security group (expiration, manual removal, or
recertification failure).

Dispatches revocation to the appropriate platform providers (Fabric,
Databricks, or both) via the provider registry. Each provider handles
its own revocation layers:
  - Fabric: workspace role removal, item revocation logging, SQL REVOKE
  - Databricks: UC REVOKE, workspace ACL removal, entitlement removal
"""

import os
import json
import logging
import azure.functions as func
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from provider_registry import get_all_providers, ProvisioningResult

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

    # Get all platform providers and dispatch revocation
    providers = get_all_providers(package)
    results: list[ProvisioningResult] = []

    for provider in providers:
        logger.info(f"Dispatching revoke to {provider.platform_name} provider")
        try:
            results.extend(provider.revoke(package, user_id, user_email))
        except Exception as e:
            logger.error(f"Provider {provider.platform_name} revocation failed: {e}")
            results.append(ProvisioningResult(
                platform=provider.platform_name, layer="dispatch",
                target="provider", action="revoke", success=False,
                detail=str(e), principal_id=user_id,
            ))

    # Build audit entry
    platforms_involved = list({r.platform for r in results})
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "revoke",
        "reason": reason,
        "user": user_email,
        "group": group_name,
        "package": package.get("package", {}).get("name", "unknown"),
        "platforms": platforms_involved,
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
            "results": [
                {"platform": r.platform, "layer": r.layer, "target": r.target,
                 "success": r.success, "detail": r.detail}
                for r in results
            ],
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
