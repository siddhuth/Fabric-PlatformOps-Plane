"""
provider_registry.py — Platform provider abstraction and factory.

Decouples Azure Functions from platform-specific API clients by providing
a common interface for provisioning, revocation, and drift detection
across Fabric, Databricks, and future platforms.

Usage:
    provider = get_provider("fabric", demo_mode=False)
    results = provider.provision(package, user_id, user_email)
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Common Result Types
# ---------------------------------------------------------------------------
@dataclass
class ProvisioningResult:
    """Result of a single permission provisioning operation."""
    platform: str       # "fabric" | "databricks" | "snowflake"
    layer: str          # "workspace" | "item" | "compute" | "identity" | "data_plane" | "control_plane"
    target: str         # Item name, securable name, or workspace ID
    action: str         # "assign_role" | "share_item" | "uc_grant" | "set_acl" | etc.
    success: bool
    detail: str
    principal_id: str


@dataclass
class DriftFinding:
    """A single drift finding from comparing declared vs actual state."""
    platform: str
    category: str       # "shadow_access" | "under_provisioned" | "over_provisioned"
    severity: str       # "high" | "medium" | "low"
    securable: str      # What resource has drift
    principal: str
    declared: str       # What the config says
    actual: str         # What the platform reports
    package: str        # Which access package this relates to


# ---------------------------------------------------------------------------
# Abstract Provider
# ---------------------------------------------------------------------------
class PlatformProvider(ABC):
    """
    Abstract base class for platform-specific permission providers.

    Each provider implements three operations:
      - provision: Grant permissions defined in an access package
      - revoke: Remove permissions defined in an access package
      - detect_drift: Compare declared state against actual platform state
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier (e.g., 'fabric', 'databricks')."""

    @abstractmethod
    def provision(self, package: dict, user_id: str,
                  user_email: str) -> list[ProvisioningResult]:
        """Provision all permissions declared in the access package."""

    @abstractmethod
    def revoke(self, package: dict, user_id: str,
               user_email: str) -> list[ProvisioningResult]:
        """Revoke all permissions declared in the access package."""

    @abstractmethod
    def detect_drift(self, packages: dict) -> list[DriftFinding]:
        """
        Compare declared access packages against actual platform state.

        Args:
            packages: Dict of {package_name: parsed_yaml_dict}

        Returns:
            List of drift findings.
        """


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------
def get_provider(platform: str, demo_mode: bool = None) -> PlatformProvider:
    """
    Get a platform provider instance.

    Args:
        platform: "fabric" | "databricks" | "snowflake"
        demo_mode: If True, return mock provider. If None, read from
                   DEMO_MODE environment variable.

    Returns:
        A PlatformProvider implementation.
    """
    if demo_mode is None:
        demo_mode = os.environ.get("DEMO_MODE", "").lower() in ("true", "1", "yes")

    if demo_mode:
        from mock_providers import get_mock_provider
        return get_mock_provider(platform)

    if platform == "fabric":
        from fabric_client import FabricProvider
        return FabricProvider.from_environment()

    if platform == "databricks":
        from databricks_client import DatabricksProvider
        return DatabricksProvider.from_environment()

    if platform == "snowflake":
        raise NotImplementedError(
            "Snowflake provider is planned for Phase 3. "
            "See docs/V2.0-LAUNCH-NOTES.md for the roadmap."
        )

    raise ValueError(f"Unknown platform: {platform}")


def get_all_providers(package: dict,
                      demo_mode: bool = None) -> list[PlatformProvider]:
    """
    Get providers for all platforms referenced in an access package.

    A package always has Fabric grants (via the 'grants' key).
    It may also have Databricks/Snowflake grants (via the 'platforms' key).

    Returns:
        List of PlatformProvider instances for each platform in the package.
    """
    providers = []

    # Fabric provider if the package has Fabric grants (items or compute)
    grants = package.get("grants", {})
    has_fabric = bool(grants.get("items") or grants.get("compute"))
    if has_fabric:
        providers.append(get_provider("fabric", demo_mode))

    # Additional platform providers
    platforms = package.get("platforms", {})
    for platform_name in platforms:
        try:
            providers.append(get_provider(platform_name, demo_mode))
        except (NotImplementedError, ValueError) as e:
            logger.warning(f"Skipping platform '{platform_name}': {e}")

    return providers
