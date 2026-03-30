#!/usr/bin/env python3
"""
validate_packages.py — CI validation for access package YAML definitions.

Validates all YAML files in access-packages/definitions/ against the JSON
schema and performs additional business logic checks:
  - Schema compliance (required fields, valid enum values)
  - Naming conventions (group names start with sg-fabric-)
  - Permission escalation detection (Viewer role + Write permissions)
  - Cross-package conflict detection (same group in multiple packages)
  - Metadata freshness (review dates not stale)
  - Databricks: UC prerequisite chain (USE CATALOG + USE SCHEMA required)
  - Databricks: No DENY enforcement (positive-permission-only)
  - Databricks: Entitlement requirements for workspace ACLs
  - Snowflake: Not-yet-supported warning

Exit code 0 = all valid, 1 = validation errors found.

Usage:
    python scripts/validate_packages.py [--strict]
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import yaml
import jsonschema

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
DEFINITIONS_DIR = REPO_ROOT / "access-packages" / "definitions"
SCHEMA_PATH = REPO_ROOT / "access-packages" / "schemas" / "access-package.schema.json"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def valid(self):
        return len(self.errors) == 0

    def error(self, filename: str, msg: str):
        self.errors.append(f"ERROR [{filename}]: {msg}")

    def warn(self, filename: str, msg: str):
        self.warnings.append(f"WARN  [{filename}]: {msg}")


def validate_all(strict: bool = False) -> ValidationResult:
    """Validate all access package definitions."""
    result = ValidationResult()

    # Load schema
    if not SCHEMA_PATH.exists():
        result.error("schema", f"Schema file not found: {SCHEMA_PATH}")
        return result

    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    # Load all packages
    packages = {}
    if not DEFINITIONS_DIR.exists():
        result.error("definitions", f"Definitions directory not found: {DEFINITIONS_DIR}")
        return result

    yaml_files = list(DEFINITIONS_DIR.glob("*.yaml"))
    if not yaml_files:
        result.error("definitions", "No YAML files found in definitions directory")
        return result

    print(f"Validating {len(yaml_files)} access package definitions...\n")

    for filepath in sorted(yaml_files):
        filename = filepath.name
        print(f"  Checking {filename}...")

        try:
            with open(filepath) as f:
                pkg = yaml.safe_load(f)
        except yaml.YAMLError as e:
            result.error(filename, f"Invalid YAML syntax: {e}")
            continue

        if not pkg:
            result.error(filename, "Empty file")
            continue

        packages[filename] = pkg

        # JSON Schema validation
        _validate_schema(pkg, schema, filename, result)

        # Business logic validation (Fabric)
        _validate_business_rules(pkg, filename, result, strict)

        # Platform-specific validation
        platforms = pkg.get("platforms", {})
        if "databricks" in platforms:
            _validate_databricks(pkg, filename, result)
        if "snowflake" in platforms:
            result.warn(filename, "Snowflake platform is not yet supported. "
                                  "Package will pass validation but cannot be provisioned.")

    # Cross-package validation
    _validate_cross_package(packages, result)

    return result


def _validate_schema(pkg: dict, schema: dict, filename: str, result: ValidationResult):
    """Validate against JSON schema."""
    try:
        jsonschema.validate(instance=pkg, schema=schema)
    except jsonschema.ValidationError as e:
        result.error(filename, f"Schema violation: {e.message} (path: {'.'.join(str(p) for p in e.path)})")
    except jsonschema.SchemaError as e:
        result.error(filename, f"Invalid schema: {e.message}")


def _validate_business_rules(pkg: dict, filename: str, result: ValidationResult, strict: bool):
    """Validate business logic rules beyond schema compliance."""

    package_config = pkg.get("package", {})
    grants = pkg.get("grants", {})
    metadata = pkg.get("metadata", {})

    # Rule 1: Group naming convention
    group_name = package_config.get("entra_group", "")
    if not group_name.startswith("sg-fabric-"):
        result.error(filename, f"Group name '{group_name}' must start with 'sg-fabric-'")

    # Rule 2: Permission escalation detection (Fabric items)
    ws_role = grants.get("workspace", {}).get("role", "")
    items = grants.get("items", [])

    if ws_role == "Viewer":
        for item in items:
            perms = item.get("permissions", [])
            if any(p in perms for p in ["Write", "Execute"]):
                result.error(
                    filename,
                    f"Permission escalation: Viewer workspace role cannot have "
                    f"Write/Execute on item '{item.get('name')}'. "
                    f"Change workspace role to Contributor or remove elevated permissions."
                )

    # Rule 3: Service account validation
    if "service-account" in filename or package_config.get("approval_policy") == "platform-team-only":
        if package_config.get("expiration_days") is not None:
            result.warn(filename, "Service accounts typically should not have expiration_days set. "
                                  "Use recertification_required in metadata instead.")

    # Rule 4: Metadata freshness
    last_reviewed = metadata.get("last_reviewed")
    review_cadence = metadata.get("review_cadence_days", 180)
    if last_reviewed:
        try:
            review_date = datetime.strptime(last_reviewed, "%Y-%m-%d")
            days_since = (datetime.now() - review_date).days
            if days_since > review_cadence:
                msg = (f"Access package review overdue: last reviewed {last_reviewed} "
                       f"({days_since} days ago, cadence is {review_cadence} days)")
                if strict:
                    result.error(filename, msg)
                else:
                    result.warn(filename, msg)
        except ValueError:
            result.error(filename, f"Invalid date format for last_reviewed: {last_reviewed}")

    # Rule 5: Version format
    version = package_config.get("version", "")
    if version and not all(c.isdigit() or c == '.' for c in version.strip('"')):
        result.error(filename, f"Version '{version}' must be numeric (e.g., '1.0', '2.3')")

    # Rule 6: Ensure items reference valid types
    valid_types = {
        "MirroredDatabase", "Lakehouse", "Warehouse", "SemanticModel",
        "Report", "DataPipeline", "Notebook", "SQLEndpoint",
        "KQLDatabase", "Eventstream", "MLModel",
    }
    for item in items:
        item_type = item.get("type", "")
        if item_type not in valid_types:
            result.error(filename, f"Unknown item type: '{item_type}'")


# ---------------------------------------------------------------------------
# Databricks-Specific Validation
# ---------------------------------------------------------------------------
def _validate_databricks(pkg: dict, filename: str, result: ValidationResult):
    """Validate Databricks-specific business rules."""
    db_config = pkg["platforms"]["databricks"]

    # Rule DB-1: SCIM group identity is required
    identity = db_config.get("identity", {})
    if not identity.get("scim_group"):
        result.error(filename, "Databricks packages require identity.scim_group "
                               "for account-level SCIM provisioning")

    # Rule DB-2: workspace-access entitlement required if workspace_acls declared
    entitlements = db_config.get("entitlements", [])
    workspace_acls = db_config.get("workspace_acls", [])
    if workspace_acls and "workspace-access" not in entitlements:
        result.error(filename, "Databricks packages with workspace_acls must include "
                               "'workspace-access' entitlement")

    # Rule DB-3: databricks-sql-access required if SQLWarehouse ACL declared
    has_sql_warehouse = any(
        acl.get("object_type") == "SQLWarehouse" for acl in workspace_acls
    )
    if has_sql_warehouse and "databricks-sql-access" not in entitlements:
        result.error(filename, "Databricks packages with SQLWarehouse ACLs must include "
                               "'databricks-sql-access' entitlement")

    # Rule DB-4: Unity Catalog prerequisite chain enforcement
    uc_config = db_config.get("unity_catalog", {})
    uc_grants = uc_config.get("grants", [])
    _validate_uc_prerequisite_chain(uc_grants, filename, result)

    # Rule DB-5: No DENY in Unity Catalog (positive-permission-only)
    # This is enforced by the schema (no deny[] field), but check for
    # any grant statements that contain DENY as a string pattern
    for grant in uc_grants:
        for priv in grant.get("privileges", []):
            if "DENY" in priv.upper():
                result.error(filename, f"Unity Catalog does not support DENY. "
                                       f"Found '{priv}' on {grant.get('securable_name')}. "
                                       f"Use REVOKE or omit the grant instead.")


def _validate_uc_prerequisite_chain(uc_grants: list[dict], filename: str,
                                     result: ValidationResult):
    """
    Validate that Unity Catalog grants have the required prerequisite chain.

    UC requires USE_CATALOG on the catalog and USE_SCHEMA on the schema
    before any object-level privilege takes effect. This rule ensures
    that access packages declare the full chain explicitly.
    """
    # Build sets of what's granted
    catalog_use = set()      # catalogs with USE_CATALOG
    schema_use = set()       # schemas with USE_SCHEMA (as "catalog.schema")

    for grant in uc_grants:
        securable_type = grant.get("securable_type", "")
        securable_name = grant.get("securable_name", "")
        privileges = grant.get("privileges", [])

        if securable_type == "Catalog" and "USE_CATALOG" in privileges:
            catalog_use.add(securable_name)

        if securable_type == "Schema" and "USE_SCHEMA" in privileges:
            schema_use.add(securable_name)

    # Check that every schema-level grant has a corresponding USE_CATALOG
    for grant in uc_grants:
        securable_type = grant.get("securable_type", "")
        securable_name = grant.get("securable_name", "")
        privileges = grant.get("privileges", [])

        # Skip catalog-level and metastore-level securables
        if securable_type in ("Catalog", "ExternalLocation", "StorageCredential", "Connection"):
            continue

        parts = securable_name.split(".")
        if len(parts) < 2:
            continue

        catalog_name = parts[0]
        schema_full_name = f"{parts[0]}.{parts[1]}"

        # Check USE_CATALOG prerequisite
        if catalog_name not in catalog_use:
            result.error(
                filename,
                f"UC prerequisite missing: grant on {securable_type} "
                f"'{securable_name}' requires USE_CATALOG on '{catalog_name}' "
                f"(not declared in this package)"
            )

        # Check USE_SCHEMA prerequisite for object-level grants
        # (Tables, Views, Volumes, Functions, Models — anything below schema level)
        if securable_type not in ("Schema",):
            if schema_full_name not in schema_use:
                result.error(
                    filename,
                    f"UC prerequisite missing: grant on {securable_type} "
                    f"'{securable_name}' requires USE_SCHEMA on "
                    f"'{schema_full_name}' (not declared in this package)"
                )


# ---------------------------------------------------------------------------
# Cross-Package Validation
# ---------------------------------------------------------------------------
def _validate_cross_package(packages: dict, result: ValidationResult):
    """Validate rules that span multiple packages."""
    # Rule: No two packages should use the same Entra group
    # UNLESS one is Fabric-only and the other is Databricks-only
    # (same Entra group can grant access to both platforms)
    group_to_packages = {}
    for filename, pkg in packages.items():
        group = pkg.get("package", {}).get("entra_group", "")
        has_databricks = "databricks" in pkg.get("platforms", {})
        has_fabric_grants = bool(pkg.get("grants", {}).get("items"))
        platform_key = "databricks" if (has_databricks and not has_fabric_grants) else "fabric"
        if group:
            group_to_packages.setdefault(group, []).append((filename, platform_key))

    for group, entries in group_to_packages.items():
        # Group entries by platform
        platforms_seen = {}
        for filename, platform in entries:
            platforms_seen.setdefault(platform, []).append(filename)

        # Error if same group + same platform in multiple packages
        for platform, files in platforms_seen.items():
            if len(files) > 1:
                result.error(
                    "cross-package",
                    f"Entra group '{group}' is used by multiple {platform} packages: "
                    f"{', '.join(files)}. Each access package must have a unique "
                    f"security group per platform."
                )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Validate access package definitions")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (for CI enforcement)")
    args = parser.parse_args()

    result = validate_all(strict=args.strict)

    # Print results
    print()
    for warning in result.warnings:
        print(f"  {warning}")
    for error in result.errors:
        print(f"  {error}")

    total_issues = len(result.errors) + len(result.warnings)
    print()
    if result.valid:
        print(f"  PASS: All access packages are valid ({len(result.warnings)} warnings)")
    else:
        print(f"  FAIL: {len(result.errors)} errors, {len(result.warnings)} warnings")

    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
