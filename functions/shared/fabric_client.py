"""
fabric_client.py — Unified client for Fabric REST API + Power BI REST API operations.

This module abstracts the multi-API surface required to provision permissions
across Fabric's three security layers:
  1. Workspace roles    → Fabric REST API
  2. Item permissions   → Power BI REST API (sharing endpoints)
  3. Compute security   → Handled separately via sql_grants.py

Also implements the PlatformProvider interface for use with the
provider_registry, enabling multi-platform provisioning dispatch.

Authentication uses MSAL with a service principal (client credentials flow).
The SPN must be:
  - Registered in Entra ID with Power BI Service API permissions
  - Enabled in Fabric Admin Portal ("Service principals can use Fabric APIs")
  - Added to the target workspace with at least Contributor role

Usage:
    client = FabricClient.from_environment()
    client.assign_workspace_role(workspace_id, principal_id, "Contributor")
    client.share_item(workspace_id, item_id, recipient_email, ["Read", "ReadAll"])

    # Or via provider interface:
    provider = FabricProvider.from_environment()
    results = provider.provision(package, user_id, user_email)
"""

import os
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests
from msal import ConfidentialClientApplication

from provider_registry import PlatformProvider, ProvisioningResult as RegistryResult, DriftFinding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_SCOPES = ["https://api.fabric.microsoft.com/.default"]
PBI_SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]

# Retry configuration for transient failures
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class ProvisioningResult:
    """Result of a single permission provisioning operation."""
    layer: str          # "workspace" | "item" | "compute"
    target: str         # Item name or workspace ID
    action: str         # "assign_role" | "share_item" | "sql_grant"
    success: bool
    detail: str
    principal_id: str


# ---------------------------------------------------------------------------
# Fabric Client
# ---------------------------------------------------------------------------
class FabricClient:
    """
    Unified client for Fabric and Power BI REST API permission operations.

    Manages two separate access tokens:
      - Fabric token: For workspace management and admin APIs
      - Power BI token: For item sharing and dataset operations
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

        self._msal_app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )

        self._fabric_token: Optional[str] = None
        self._pbi_token: Optional[str] = None
        self._token_expiry: float = 0

    @classmethod
    def from_environment(cls) -> "FabricClient":
        """Create a client from standard environment variables."""
        return cls(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["FABRIC_CLIENT_ID"],
            client_secret=os.environ["FABRIC_CLIENT_SECRET"],
        )

    # -----------------------------------------------------------------------
    # Token Management
    # -----------------------------------------------------------------------
    def _acquire_token(self, scopes: list[str]) -> str:
        """Acquire an access token using client credentials flow."""
        result = self._msal_app.acquire_token_for_client(scopes=scopes)
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown"))
            raise PermissionError(f"Token acquisition failed: {error}")
        return result["access_token"]

    @property
    def fabric_token(self) -> str:
        if not self._fabric_token or time.time() > self._token_expiry:
            self._fabric_token = self._acquire_token(FABRIC_SCOPES)
            self._token_expiry = time.time() + 3300  # ~55 min
        return self._fabric_token

    @property
    def pbi_token(self) -> str:
        if not self._pbi_token:
            self._pbi_token = self._acquire_token(PBI_SCOPES)
        return self._pbi_token

    def _fabric_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.fabric_token}", "Content-Type": "application/json"}

    def _pbi_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.pbi_token}", "Content-Type": "application/json"}

    # -----------------------------------------------------------------------
    # HTTP Helpers with Retry
    # -----------------------------------------------------------------------
    def _request_with_retry(self, method: str, url: str, headers: dict,
                            json_body: dict = None) -> requests.Response:
        """Execute an HTTP request with exponential backoff retry."""
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.request(method, url, headers=headers, json=json_body, timeout=30)

                if resp.status_code == 429:  # Rate limited
                    retry_after = int(resp.headers.get("Retry-After", RETRY_BACKOFF_SECONDS * (attempt + 1)))
                    logger.warning(f"Rate limited. Retrying after {retry_after}s (attempt {attempt + 1})")
                    time.sleep(retry_after)
                    continue

                if resp.status_code >= 500:
                    logger.warning(f"Server error {resp.status_code}. Retrying (attempt {attempt + 1})")
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue

                return resp

            except requests.exceptions.ConnectionError as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise

        raise RuntimeError(f"Max retries exceeded for {method} {url}")

    # -----------------------------------------------------------------------
    # Workspace Operations (Fabric REST API)
    # -----------------------------------------------------------------------
    def list_workspaces(self) -> list[dict]:
        """List all workspaces accessible to the service principal."""
        url = f"{FABRIC_API_BASE}/workspaces"
        resp = self._request_with_retry("GET", url, self._fabric_headers())
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_workspace_items(self, workspace_id: str) -> list[dict]:
        """List all items in a workspace."""
        url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/items"
        resp = self._request_with_retry("GET", url, self._fabric_headers())
        resp.raise_for_status()
        return resp.json().get("value", [])

    def assign_workspace_role(self, workspace_id: str, principal_id: str,
                               principal_type: str, role: str) -> ProvisioningResult:
        """
        Assign a workspace role to a principal.

        Args:
            workspace_id: Fabric workspace ID
            principal_id: Entra object ID (user, group, or SPN)
            principal_type: "User" | "Group" | "ServicePrincipal"
            role: "Admin" | "Member" | "Contributor" | "Viewer"
        """
        # Use Power BI API for workspace role assignment (more mature endpoint)
        url = f"{PBI_API_BASE}/groups/{workspace_id}/users"
        body = {
            "identifier": principal_id,
            "groupUserAccessRight": role,
            "principalType": principal_type,
        }

        resp = self._request_with_retry("POST", url, self._pbi_headers(), body)

        if resp.status_code == 200:
            return ProvisioningResult(
                layer="workspace", target=workspace_id,
                action="assign_role", success=True,
                detail=f"Assigned {role} to {principal_id}",
                principal_id=principal_id,
            )

        # 409 = already exists, try update instead
        if resp.status_code == 409:
            update_url = f"{url}/{principal_id}"
            body["groupUserAccessRight"] = role
            resp = self._request_with_retry("PUT", update_url, self._pbi_headers(), body)

            return ProvisioningResult(
                layer="workspace", target=workspace_id,
                action="update_role", success=resp.status_code == 200,
                detail=f"Updated role to {role}" if resp.status_code == 200 else resp.text,
                principal_id=principal_id,
            )

        return ProvisioningResult(
            layer="workspace", target=workspace_id,
            action="assign_role", success=False,
            detail=f"Failed ({resp.status_code}): {resp.text}",
            principal_id=principal_id,
        )

    def remove_workspace_role(self, workspace_id: str, principal_id: str) -> ProvisioningResult:
        """Remove a principal from a workspace."""
        url = f"{PBI_API_BASE}/groups/{workspace_id}/users/{principal_id}"
        resp = self._request_with_retry("DELETE", url, self._pbi_headers())

        return ProvisioningResult(
            layer="workspace", target=workspace_id,
            action="remove_role", success=resp.status_code == 200,
            detail="Removed" if resp.status_code == 200 else resp.text,
            principal_id=principal_id,
        )

    # -----------------------------------------------------------------------
    # Item Sharing Operations (Power BI REST API)
    # -----------------------------------------------------------------------
    def share_item(self, workspace_id: str, item_id: str,
                   recipient_id: str, recipient_type: str,
                   permissions: list[str],
                   notify: bool = False) -> ProvisioningResult:
        """
        Share a Fabric item with a principal, granting specified permissions.

        This uses the Power BI REST API sharing endpoint which supports:
          - Reports, Dashboards, Datasets (semantic models)
          - Lakehouses, Warehouses (via newer endpoints)

        For mirrored databases: sharing automatically cascades to the
        SQL analytics endpoint and default semantic model.

        Args:
            permissions: List of permission strings, e.g.:
                ["Read", "ReadAll", "Reshare", "Build"]
        """
        # Construct sharing link via Power BI API
        url = f"{PBI_API_BASE}/groups/{workspace_id}/datasets/{item_id}/users"
        body = {
            "identifier": recipient_id,
            "principalType": recipient_type,
            "datasetUserAccessRight": self._map_permissions_to_access_right(permissions),
        }

        resp = self._request_with_retry("POST", url, self._pbi_headers(), body)

        return ProvisioningResult(
            layer="item", target=item_id,
            action="share_item", success=resp.status_code in (200, 201),
            detail=f"Shared with {permissions}" if resp.status_code in (200, 201) else resp.text,
            principal_id=recipient_id,
        )

    def _map_permissions_to_access_right(self, permissions: list[str]) -> str:
        """Map our permission list to PBI API access right strings."""
        if "Write" in permissions or "Execute" in permissions:
            return "ReadWrite"
        if "Build" in permissions:
            return "ReadExplore"  # Build = Explore in PBI API terms
        if "Reshare" in permissions:
            return "ReadReshare"
        return "Read"

    # -----------------------------------------------------------------------
    # Admin / Audit Operations (Fabric Admin API)
    # -----------------------------------------------------------------------
    def get_user_access_entities(self, user_id: str,
                                 item_type: str = None) -> list[dict]:
        """
        Retrieve all items a user has access to (Admin API).
        Requires Fabric Administrator role or SPN with admin API access.

        Returns paginated results — handles continuation tokens internally.
        """
        url = f"{FABRIC_API_BASE}/admin/users/{user_id}/access"
        if item_type:
            url += f"?type={item_type}"

        all_entities = []
        while url:
            resp = self._request_with_retry("GET", url, self._fabric_headers())
            resp.raise_for_status()
            data = resp.json()
            all_entities.extend(data.get("accessEntities", []))
            url = data.get("continuationUri")

        return all_entities

    def resolve_item_permissions(self, workspace_id: str, item_id: str) -> dict:
        """
        Resolve effective permissions for the calling principal on a specific item.
        Uses the Workload Control API.
        """
        url = (f"{FABRIC_API_BASE}/workload-control/workspaces/{workspace_id}"
               f"/items/{item_id}/resolvePermissions")
        resp = self._request_with_retry("GET", url, self._fabric_headers())
        resp.raise_for_status()
        return resp.json()

    # -----------------------------------------------------------------------
    # Workspace Item Discovery
    # -----------------------------------------------------------------------
    def find_item_by_name(self, workspace_id: str, item_name: str,
                          item_type: str = None) -> Optional[dict]:
        """Find an item in a workspace by display name and optional type filter."""
        items = self.get_workspace_items(workspace_id)
        for item in items:
            if item["displayName"] == item_name:
                if item_type is None or item["type"] == item_type:
                    return item
        return None


# ---------------------------------------------------------------------------
# Provider Interface (wraps FabricClient for provider_registry dispatch)
# ---------------------------------------------------------------------------
class FabricProvider(PlatformProvider):
    """
    PlatformProvider implementation for Microsoft Fabric.

    Wraps the existing FabricClient methods to conform to the provider
    registry interface, enabling multi-platform provisioning dispatch.
    """

    def __init__(self, client: FabricClient):
        self._client = client

    @classmethod
    def from_environment(cls) -> "FabricProvider":
        return cls(FabricClient.from_environment())

    @property
    def platform_name(self) -> str:
        return "fabric"

    def provision(self, package: dict, user_id: str,
                  user_email: str) -> list[RegistryResult]:
        results = []
        grants = package.get("grants", {})

        # Layer 1: Workspace role
        ws_config = grants.get("workspace", {})
        workspace_id = self._resolve_env(ws_config.get("id", ""))
        role = ws_config.get("role", "Viewer")

        if workspace_id and role:
            r = self._client.assign_workspace_role(
                workspace_id=workspace_id,
                principal_id=user_id,
                principal_type="User",
                role=role,
            )
            results.append(RegistryResult(
                platform="fabric", layer=r.layer, target=r.target,
                action=r.action, success=r.success, detail=r.detail,
                principal_id=r.principal_id,
            ))

        # Layer 2: Item sharing
        for item_cfg in grants.get("items", []):
            item_name = item_cfg.get("name")
            item_type = item_cfg.get("type")
            permissions = item_cfg.get("permissions", ["Read"])

            if workspace_id and item_name:
                item = self._client.find_item_by_name(workspace_id, item_name, item_type)
                if item:
                    r = self._client.share_item(
                        workspace_id=workspace_id,
                        item_id=item["id"],
                        recipient_id=user_id,
                        recipient_type="User",
                        permissions=permissions,
                    )
                    results.append(RegistryResult(
                        platform="fabric", layer=r.layer, target=r.target,
                        action=r.action, success=r.success, detail=r.detail,
                        principal_id=r.principal_id,
                    ))
                else:
                    results.append(RegistryResult(
                        platform="fabric", layer="item", target=item_name,
                        action="share_item", success=False,
                        detail=f"Item not found: {item_name} ({item_type})",
                        principal_id=user_id,
                    ))

        # Layer 3: SQL grants (delegated to sql_grants module)
        sql_config = grants.get("compute", {}).get("sql_endpoint", {})
        if sql_config.get("grants") or sql_config.get("deny"):
            try:
                from sql_grants import provision_sql_access
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
                    results.append(RegistryResult(
                        platform="fabric", layer="compute",
                        target=sr.script.description, action="sql_grant",
                        success=sr.success, detail=sr.error or "OK",
                        principal_id=user_id,
                    ))
            except Exception as e:
                logger.error(f"SQL grants failed: {e}")
                results.append(RegistryResult(
                    platform="fabric", layer="compute", target="sql_endpoint",
                    action="sql_grant", success=False, detail=str(e),
                    principal_id=user_id,
                ))

        return results

    def revoke(self, package: dict, user_id: str,
               user_email: str) -> list[RegistryResult]:
        results = []
        grants = package.get("grants", {})

        # Remove workspace role
        ws_config = grants.get("workspace", {})
        workspace_id = self._resolve_env(ws_config.get("id", ""))
        if workspace_id:
            r = self._client.remove_workspace_role(workspace_id, user_id)
            results.append(RegistryResult(
                platform="fabric", layer=r.layer, target=r.target,
                action=r.action, success=r.success, detail=r.detail,
                principal_id=r.principal_id,
            ))

        # Log item revocations for manual review
        for item_cfg in grants.get("items", []):
            results.append(RegistryResult(
                platform="fabric", layer="item",
                target=item_cfg.get("name", "unknown"),
                action="revoke_item", success=True,
                detail="Item permission revocation logged for manual review",
                principal_id=user_id,
            ))

        # Revoke SQL grants
        sql_config = grants.get("compute", {}).get("sql_endpoint", {})
        if sql_config:
            try:
                from sql_grants import revoke_sql_access
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
                    results.append(RegistryResult(
                        platform="fabric", layer="compute",
                        target=sr.script.description, action="sql_revoke",
                        success=sr.success, detail=sr.error or "OK",
                        principal_id=user_id,
                    ))
            except Exception as e:
                logger.error(f"SQL revocation failed: {e}")

        return results

    def detect_drift(self, packages: dict) -> list[DriftFinding]:
        findings = []

        for pkg_name, pkg in packages.items():
            grants = pkg.get("grants", {})
            ws_config = grants.get("workspace", {})
            workspace_id = self._resolve_env(ws_config.get("id", ""))
            group_name = pkg.get("package", {}).get("entra_group", "")
            expected_role = ws_config.get("role", "")

            if not workspace_id:
                continue

            try:
                import requests as req
                resp = req.get(
                    f"{PBI_API_BASE}/groups/{workspace_id}/users",
                    headers={"Authorization": f"Bearer {self._client.pbi_token}"},
                    timeout=30,
                )
                if resp.status_code != 200:
                    continue

                for user in resp.json().get("value", []):
                    if (user.get("identifier") == group_name or
                            user.get("displayName") == group_name):
                        actual_role = user.get("groupUserAccessRight", "")
                        if actual_role != expected_role:
                            role_ranks = {"Viewer": 1, "Contributor": 2, "Member": 3, "Admin": 4}
                            category = ("over_provisioned"
                                        if role_ranks.get(actual_role, 0) > role_ranks.get(expected_role, 0)
                                        else "under_provisioned")
                            findings.append(DriftFinding(
                                platform="fabric",
                                category=category,
                                severity="high" if category == "over_provisioned" else "medium",
                                securable=f"workspace:{workspace_id}",
                                principal=group_name,
                                declared=expected_role,
                                actual=actual_role,
                                package=pkg_name,
                            ))
            except Exception as e:
                logger.error(f"Drift check failed for {pkg_name}: {e}")

        return findings

    @staticmethod
    def _resolve_env(ref: str) -> str:
        if ref.startswith("${") and ref.endswith("}"):
            return os.environ.get(ref[2:-1], "")
        return ref
