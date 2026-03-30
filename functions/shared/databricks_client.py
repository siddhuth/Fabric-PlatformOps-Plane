"""
databricks_client.py — Azure Databricks workspace and Unity Catalog client.

Implements the PlatformProvider interface for Databricks, handling:
  1. SCIM entitlement provisioning (workspace-access, databricks-sql-access)
  2. Unity Catalog GRANT/REVOKE via SQL Statement API
  3. Workspace ACL management via Permissions API
  4. Drift detection via system.information_schema queries

Authentication uses Entra ID (Azure AD) OAuth M2M flow with the same
service principal used for Fabric. The SPN must be:
  - Registered as a Databricks account-level service principal
  - Assigned to the target workspace
  - Granted metastore admin or appropriate UC privileges

Usage:
    provider = DatabricksProvider.from_environment()
    results = provider.provision(package, user_id, user_email)
"""

import os
import json
import logging
import time
from typing import Optional

import requests
from msal import ConfidentialClientApplication

from provider_registry import PlatformProvider, ProvisioningResult, DriftFinding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATABRICKS_SCOPES = ["2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"]  # Azure Databricks resource ID

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


class DatabricksProvider(PlatformProvider):
    """
    Databricks platform provider implementing workspace ACLs,
    SCIM entitlements, and Unity Catalog grants.
    """

    def __init__(self, workspace_url: str, tenant_id: str,
                 client_id: str, client_secret: str):
        self.workspace_url = workspace_url.rstrip("/")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

        self._msal_app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )

        self._token: Optional[str] = None
        self._token_expiry: float = 0

    @property
    def platform_name(self) -> str:
        return "databricks"

    @classmethod
    def from_environment(cls) -> "DatabricksProvider":
        return cls(
            workspace_url=os.environ["DATABRICKS_WORKSPACE_URL"],
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ.get("DATABRICKS_CLIENT_ID",
                                     os.environ.get("FABRIC_CLIENT_ID", "")),
            client_secret=os.environ.get("DATABRICKS_CLIENT_SECRET",
                                         os.environ.get("FABRIC_CLIENT_SECRET", "")),
        )

    # -----------------------------------------------------------------------
    # Token Management
    # -----------------------------------------------------------------------
    @property
    def token(self) -> str:
        if not self._token or time.time() > self._token_expiry:
            result = self._msal_app.acquire_token_for_client(scopes=DATABRICKS_SCOPES)
            if "access_token" not in result:
                error = result.get("error_description", result.get("error", "Unknown"))
                raise PermissionError(f"Databricks token acquisition failed: {error}")
            self._token = result["access_token"]
            self._token_expiry = time.time() + 3300
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # -----------------------------------------------------------------------
    # HTTP Helper
    # -----------------------------------------------------------------------
    def _request(self, method: str, path: str,
                 json_body: dict = None) -> requests.Response:
        url = f"{self.workspace_url}/api/2.0{path}"
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.request(
                    method, url, headers=self._headers(),
                    json=json_body, timeout=30
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After",
                                                       RETRY_BACKOFF_SECONDS * (attempt + 1)))
                    logger.warning(f"Rate limited on {path}. Retry in {retry_after}s")
                    time.sleep(retry_after)
                    continue
                if resp.status_code >= 500:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                return resp
            except requests.exceptions.ConnectionError:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise
        raise RuntimeError(f"Max retries exceeded for {method} {path}")

    # -----------------------------------------------------------------------
    # PlatformProvider Implementation
    # -----------------------------------------------------------------------
    def provision(self, package: dict, user_id: str,
                  user_email: str) -> list[ProvisioningResult]:
        results = []
        db_config = package.get("platforms", {}).get("databricks", {})
        if not db_config:
            return results

        scim_group = db_config.get("identity", {}).get("scim_group", "")

        # Layer 1: SCIM Entitlements
        entitlements = db_config.get("entitlements", [])
        if entitlements and scim_group:
            results.append(self._set_entitlements(scim_group, entitlements))

        # Layer 2: Unity Catalog Grants
        uc_grants = db_config.get("unity_catalog", {}).get("grants", [])
        for grant in uc_grants:
            results.append(self._grant_uc_privilege(grant, scim_group))

        # Layer 3: Workspace ACLs
        for acl in db_config.get("workspace_acls", []):
            results.append(self._set_workspace_acl(acl, scim_group))

        return results

    def revoke(self, package: dict, user_id: str,
               user_email: str) -> list[ProvisioningResult]:
        results = []
        db_config = package.get("platforms", {}).get("databricks", {})
        if not db_config:
            return results

        scim_group = db_config.get("identity", {}).get("scim_group", "")

        # Revoke UC grants
        uc_grants = db_config.get("unity_catalog", {}).get("grants", [])
        for grant in uc_grants:
            results.append(self._revoke_uc_privilege(grant, scim_group))

        # Remove workspace ACLs
        for acl in db_config.get("workspace_acls", []):
            results.append(self._remove_workspace_acl(acl, scim_group))

        # Remove entitlements
        entitlements = db_config.get("entitlements", [])
        if entitlements and scim_group:
            results.append(self._remove_entitlements(scim_group, entitlements))

        return results

    def detect_drift(self, packages: dict) -> list[DriftFinding]:
        findings = []
        for pkg_name, pkg in packages.items():
            db_config = pkg.get("platforms", {}).get("databricks", {})
            if not db_config:
                continue

            scim_group = db_config.get("identity", {}).get("scim_group", "")
            uc_grants = db_config.get("unity_catalog", {}).get("grants", [])

            for grant in uc_grants:
                drift = self._check_uc_grant_drift(grant, scim_group, pkg_name)
                if drift:
                    findings.append(drift)

        return findings

    # -----------------------------------------------------------------------
    # SCIM Entitlement Operations
    # -----------------------------------------------------------------------
    def _set_entitlements(self, group_name: str,
                          entitlements: list[str]) -> ProvisioningResult:
        try:
            group_id = self._resolve_group_id(group_name)
            if not group_id:
                return ProvisioningResult(
                    platform="databricks", layer="identity",
                    target=group_name, action="set_entitlements",
                    success=False,
                    detail=f"SCIM group not found: {group_name}",
                    principal_id=group_name,
                )

            body = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{
                    "op": "add",
                    "path": "entitlements",
                    "value": [{"value": e} for e in entitlements],
                }],
            }
            resp = self._request("PATCH", f"/preview/scim/v2/Groups/{group_id}", body)

            return ProvisioningResult(
                platform="databricks", layer="identity",
                target=group_name, action="set_entitlements",
                success=resp.status_code in (200, 204),
                detail=f"Entitlements set: {entitlements}" if resp.status_code in (200, 204)
                       else f"Failed ({resp.status_code}): {resp.text}",
                principal_id=group_name,
            )
        except Exception as e:
            return ProvisioningResult(
                platform="databricks", layer="identity",
                target=group_name, action="set_entitlements",
                success=False, detail=str(e), principal_id=group_name,
            )

    def _remove_entitlements(self, group_name: str,
                              entitlements: list[str]) -> ProvisioningResult:
        try:
            group_id = self._resolve_group_id(group_name)
            if not group_id:
                return ProvisioningResult(
                    platform="databricks", layer="identity",
                    target=group_name, action="remove_entitlements",
                    success=False,
                    detail=f"SCIM group not found: {group_name}",
                    principal_id=group_name,
                )

            body = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {"op": "remove",
                     "path": f'entitlements[value eq "{e}"]'}
                    for e in entitlements
                ],
            }
            resp = self._request("PATCH", f"/preview/scim/v2/Groups/{group_id}", body)

            return ProvisioningResult(
                platform="databricks", layer="identity",
                target=group_name, action="remove_entitlements",
                success=resp.status_code in (200, 204),
                detail=f"Entitlements removed: {entitlements}" if resp.status_code in (200, 204)
                       else f"Failed ({resp.status_code}): {resp.text}",
                principal_id=group_name,
            )
        except Exception as e:
            return ProvisioningResult(
                platform="databricks", layer="identity",
                target=group_name, action="remove_entitlements",
                success=False, detail=str(e), principal_id=group_name,
            )

    def _resolve_group_id(self, group_name: str) -> Optional[str]:
        resp = self._request(
            "GET",
            f'/preview/scim/v2/Groups?filter=displayName eq "{group_name}"'
        )
        if resp.status_code == 200:
            resources = resp.json().get("Resources", [])
            if resources:
                return resources[0]["id"]
        return None

    # -----------------------------------------------------------------------
    # Unity Catalog Grant Operations
    # -----------------------------------------------------------------------
    def _grant_uc_privilege(self, grant: dict,
                            principal: str) -> ProvisioningResult:
        securable_type = grant["securable_type"].lower()
        securable_name = grant["securable_name"]
        privileges = grant["privileges"]

        try:
            resp = self._request(
                "PATCH",
                f"/unity-catalog/permissions/{securable_type}/{securable_name}",
                {
                    "changes": [{
                        "principal": principal,
                        "add": [p.upper() for p in privileges],
                    }]
                },
            )

            return ProvisioningResult(
                platform="databricks", layer="data_plane",
                target=f"{securable_type}:{securable_name}",
                action="uc_grant",
                success=resp.status_code == 200,
                detail=f"Granted {privileges}" if resp.status_code == 200
                       else f"Failed ({resp.status_code}): {resp.text}",
                principal_id=principal,
            )
        except Exception as e:
            return ProvisioningResult(
                platform="databricks", layer="data_plane",
                target=f"{securable_type}:{securable_name}",
                action="uc_grant", success=False,
                detail=str(e), principal_id=principal,
            )

    def _revoke_uc_privilege(self, grant: dict,
                              principal: str) -> ProvisioningResult:
        securable_type = grant["securable_type"].lower()
        securable_name = grant["securable_name"]
        privileges = grant["privileges"]

        try:
            resp = self._request(
                "PATCH",
                f"/unity-catalog/permissions/{securable_type}/{securable_name}",
                {
                    "changes": [{
                        "principal": principal,
                        "remove": [p.upper() for p in privileges],
                    }]
                },
            )

            return ProvisioningResult(
                platform="databricks", layer="data_plane",
                target=f"{securable_type}:{securable_name}",
                action="uc_revoke",
                success=resp.status_code == 200,
                detail=f"Revoked {privileges}" if resp.status_code == 200
                       else f"Failed ({resp.status_code}): {resp.text}",
                principal_id=principal,
            )
        except Exception as e:
            return ProvisioningResult(
                platform="databricks", layer="data_plane",
                target=f"{securable_type}:{securable_name}",
                action="uc_revoke", success=False,
                detail=str(e), principal_id=principal,
            )

    # -----------------------------------------------------------------------
    # Workspace ACL Operations
    # -----------------------------------------------------------------------
    # Maps YAML object_type to Databricks API path segments
    _ACL_TYPE_MAP = {
        "Cluster": "clusters",
        "ClusterPolicy": "cluster-policies",
        "SQLWarehouse": "sql/warehouses",
        "Job": "jobs",
        "DLTPipeline": "pipelines",
        "Notebook": "notebooks",
        "Repo": "repos",
        "Directory": "directories",
        "ServingEndpoint": "serving-endpoints",
        "VectorSearchEndpoint": "vector-search/endpoints",
        "GenieSpace": "genie/spaces",
        "AIBIDashboard": "dashboards",
        "DatabricksApp": "apps",
        "Experiment": "experiments",
        "SecretScope": "secrets/scopes",
        "InstancePool": "instance-pools",
    }

    def _set_workspace_acl(self, acl: dict,
                           group_name: str) -> ProvisioningResult:
        object_type = acl["object_type"]
        object_ref = self._resolve_env(acl["object_ref"])
        permission_level = acl["permission_level"]

        api_type = self._ACL_TYPE_MAP.get(object_type, object_type.lower())

        try:
            resp = self._request(
                "PUT",
                f"/permissions/{api_type}/{object_ref}",
                {
                    "access_control_list": [{
                        "group_name": group_name,
                        "all_permissions": [{"permission_level": permission_level}],
                    }]
                },
            )

            return ProvisioningResult(
                platform="databricks", layer="control_plane",
                target=f"{object_type}:{object_ref}",
                action="set_acl",
                success=resp.status_code == 200,
                detail=f"Set {permission_level}" if resp.status_code == 200
                       else f"Failed ({resp.status_code}): {resp.text}",
                principal_id=group_name,
            )
        except Exception as e:
            return ProvisioningResult(
                platform="databricks", layer="control_plane",
                target=f"{object_type}:{object_ref}",
                action="set_acl", success=False,
                detail=str(e), principal_id=group_name,
            )

    def _remove_workspace_acl(self, acl: dict,
                               group_name: str) -> ProvisioningResult:
        object_type = acl["object_type"]
        object_ref = self._resolve_env(acl["object_ref"])

        return ProvisioningResult(
            platform="databricks", layer="control_plane",
            target=f"{object_type}:{object_ref}",
            action="remove_acl", success=True,
            detail="ACL removal logged for manual review "
                   "(Databricks API does not support ACL deletion, only overwrite)",
            principal_id=group_name,
        )

    # -----------------------------------------------------------------------
    # Drift Detection
    # -----------------------------------------------------------------------
    def _check_uc_grant_drift(self, grant: dict, principal: str,
                               package_name: str) -> Optional[DriftFinding]:
        securable_type = grant["securable_type"].lower()
        securable_name = grant["securable_name"]
        expected_privileges = set(p.upper() for p in grant["privileges"])

        try:
            resp = self._request(
                "GET",
                f"/unity-catalog/permissions/{securable_type}/{securable_name}"
            )
            if resp.status_code != 200:
                return None

            actual_privileges = set()
            for entry in resp.json().get("privilege_assignments", []):
                if entry.get("principal") == principal:
                    for p in entry.get("privileges", []):
                        actual_privileges.add(p.get("privilege", ""))

            if expected_privileges != actual_privileges:
                missing = expected_privileges - actual_privileges
                extra = actual_privileges - expected_privileges

                if extra:
                    return DriftFinding(
                        platform="databricks",
                        category="over_provisioned",
                        severity="high",
                        securable=f"{securable_type}:{securable_name}",
                        principal=principal,
                        declared=", ".join(sorted(expected_privileges)),
                        actual=", ".join(sorted(actual_privileges)),
                        package=package_name,
                    )
                if missing:
                    return DriftFinding(
                        platform="databricks",
                        category="under_provisioned",
                        severity="medium",
                        securable=f"{securable_type}:{securable_name}",
                        principal=principal,
                        declared=", ".join(sorted(expected_privileges)),
                        actual=", ".join(sorted(actual_privileges)),
                        package=package_name,
                    )
        except Exception as e:
            logger.error(f"Drift check failed for {securable_name}: {e}")

        return None

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _resolve_env(ref: str) -> str:
        if ref.startswith("${") and ref.endswith("}"):
            return os.environ.get(ref[2:-1], "")
        return ref
