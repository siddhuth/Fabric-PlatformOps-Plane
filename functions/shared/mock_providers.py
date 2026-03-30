"""
mock_providers.py — Mock platform providers for demo mode.

Returns deterministic, realistic responses without requiring cloud
credentials or API access. Activated by setting DEMO_MODE=true.

Usage:
    from mock_providers import get_mock_provider
    provider = get_mock_provider("fabric")
    results = provider.provision(package, user_id, user_email)
"""

import logging
import time
from datetime import datetime, timezone

from provider_registry import PlatformProvider, ProvisioningResult, DriftFinding

logger = logging.getLogger(__name__)


class MockFabricProvider(PlatformProvider):
    """Mock Fabric provider returning realistic demo responses."""

    @property
    def platform_name(self) -> str:
        return "fabric"

    def provision(self, package: dict, user_id: str,
                  user_email: str) -> list[ProvisioningResult]:
        results = []
        grants = package.get("grants", {})

        # Mock workspace role assignment
        ws_config = grants.get("workspace", {})
        if ws_config.get("role"):
            results.append(ProvisioningResult(
                platform="fabric", layer="workspace",
                target=ws_config.get("id", "demo-workspace"),
                action="assign_role", success=True,
                detail=f"Assigned {ws_config['role']} to {user_email}",
                principal_id=user_id,
            ))

        # Mock item sharing
        for item in grants.get("items", []):
            results.append(ProvisioningResult(
                platform="fabric", layer="item",
                target=item["name"], action="share_item",
                success=True,
                detail=f"Shared with {item.get('permissions', ['Read'])}",
                principal_id=user_id,
            ))

        # Mock SQL grants
        sql_config = grants.get("compute", {}).get("sql_endpoint", {})
        for grant_stmt in sql_config.get("grants", []):
            results.append(ProvisioningResult(
                platform="fabric", layer="compute",
                target="sql_endpoint", action="sql_grant",
                success=True, detail=f"Executed: {grant_stmt[:60]}...",
                principal_id=user_id,
            ))

        return results

    def revoke(self, package: dict, user_id: str,
               user_email: str) -> list[ProvisioningResult]:
        results = []
        grants = package.get("grants", {})

        ws_config = grants.get("workspace", {})
        if ws_config.get("role"):
            results.append(ProvisioningResult(
                platform="fabric", layer="workspace",
                target=ws_config.get("id", "demo-workspace"),
                action="remove_role", success=True,
                detail=f"Removed {user_email} from workspace",
                principal_id=user_id,
            ))

        for item in grants.get("items", []):
            results.append(ProvisioningResult(
                platform="fabric", layer="item",
                target=item["name"], action="revoke_item",
                success=True,
                detail="Revocation logged for manual review",
                principal_id=user_id,
            ))

        return results

    def detect_drift(self, packages: dict) -> list[DriftFinding]:
        # Return a sample drift finding for demo purposes
        return [
            DriftFinding(
                platform="fabric",
                category="over_provisioned",
                severity="high",
                securable="workspace:sales-lakehouse-dev",
                principal="sg-fabric-analytics-sales",
                declared="Viewer",
                actual="Member",
                package="analytics-team",
            ),
            DriftFinding(
                platform="fabric",
                category="under_provisioned",
                severity="medium",
                securable="item:sales-mirror-db",
                principal="sg-fabric-do-sales",
                declared="Read",
                actual="(not shared)",
                package="data-office",
            ),
        ]


class MockDatabricksProvider(PlatformProvider):
    """Mock Databricks provider returning realistic demo responses."""

    @property
    def platform_name(self) -> str:
        return "databricks"

    def provision(self, package: dict, user_id: str,
                  user_email: str) -> list[ProvisioningResult]:
        results = []
        db_config = package.get("platforms", {}).get("databricks", {})
        if not db_config:
            return results

        scim_group = db_config.get("identity", {}).get("scim_group", "unknown")

        # Mock entitlement assignment
        entitlements = db_config.get("entitlements", [])
        if entitlements:
            results.append(ProvisioningResult(
                platform="databricks", layer="identity",
                target=scim_group, action="set_entitlements",
                success=True,
                detail=f"Entitlements set: {entitlements}",
                principal_id=scim_group,
            ))

        # Mock UC grants
        for grant in db_config.get("unity_catalog", {}).get("grants", []):
            results.append(ProvisioningResult(
                platform="databricks", layer="data_plane",
                target=f"{grant['securable_type']}:{grant['securable_name']}",
                action="uc_grant", success=True,
                detail=f"Granted {grant['privileges']}",
                principal_id=scim_group,
            ))

        # Mock workspace ACLs
        for acl in db_config.get("workspace_acls", []):
            results.append(ProvisioningResult(
                platform="databricks", layer="control_plane",
                target=f"{acl['object_type']}:{acl['object_ref']}",
                action="set_acl", success=True,
                detail=f"Set {acl['permission_level']}",
                principal_id=scim_group,
            ))

        return results

    def revoke(self, package: dict, user_id: str,
               user_email: str) -> list[ProvisioningResult]:
        results = []
        db_config = package.get("platforms", {}).get("databricks", {})
        if not db_config:
            return results

        scim_group = db_config.get("identity", {}).get("scim_group", "unknown")

        for grant in db_config.get("unity_catalog", {}).get("grants", []):
            results.append(ProvisioningResult(
                platform="databricks", layer="data_plane",
                target=f"{grant['securable_type']}:{grant['securable_name']}",
                action="uc_revoke", success=True,
                detail=f"Revoked {grant['privileges']}",
                principal_id=scim_group,
            ))

        entitlements = db_config.get("entitlements", [])
        if entitlements:
            results.append(ProvisioningResult(
                platform="databricks", layer="identity",
                target=scim_group, action="remove_entitlements",
                success=True,
                detail=f"Entitlements removed: {entitlements}",
                principal_id=scim_group,
            ))

        return results

    def detect_drift(self, packages: dict) -> list[DriftFinding]:
        return [
            DriftFinding(
                platform="databricks",
                category="shadow_access",
                severity="high",
                securable="table:sales_catalog.raw.customer_pii",
                principal="user@contoso.com",
                declared="(not in any package)",
                actual="SELECT",
                package="(none)",
            ),
            DriftFinding(
                platform="databricks",
                category="under_provisioned",
                severity="medium",
                securable="schema:sales_catalog.staging",
                principal="sg-fabric-de-sales",
                declared="USE_SCHEMA, SELECT, MODIFY",
                actual="USE_SCHEMA, SELECT",
                package="databricks-engineer",
            ),
            DriftFinding(
                platform="databricks",
                category="over_provisioned",
                severity="high",
                securable="schema:ml_catalog.models",
                principal="sg-fabric-ml-sales",
                declared="USE_SCHEMA, CREATE_MODEL, SELECT",
                actual="USE_SCHEMA, CREATE_MODEL, SELECT, MODIFY, ALL_PRIVILEGES",
                package="databricks-ml-team",
            ),
        ]


def get_mock_provider(platform: str) -> PlatformProvider:
    """Get a mock provider for the specified platform."""
    providers = {
        "fabric": MockFabricProvider,
        "databricks": MockDatabricksProvider,
    }

    provider_cls = providers.get(platform)
    if not provider_cls:
        raise NotImplementedError(
            f"Mock provider not available for '{platform}'. "
            f"Available: {', '.join(providers.keys())}"
        )

    return provider_cls()
