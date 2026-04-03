#!/usr/bin/env python3
"""
generate_fixtures.py — Reads actual YAML access packages and produces
consistent synthetic fixture data for the control plane UI demo.

Usage:
    python demo/generate_fixtures.py [--seed 42] [--output-dir demo/fixtures]

Fixtures produced:
    - access-matrix.json        Cross-platform access matrix (principals × resources)
    - audit-log.json            30-day audit history with 50+ events
    - drift-results.json        8-10 drift findings across both platforms
    - provisioning-events.json  3-4 complete provisioning traces
    - platform-summary.json     Platform stats and status
    - system-table-samples.json Databricks system table samples
"""

import argparse
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PACKAGES_DIR = Path(__file__).resolve().parent.parent / "access-packages" / "definitions"
OUTPUT_DIR = Path(__file__).resolve().parent / "fixtures"

# Synthetic identity corpus
USERS = [
    {"id": "u-001", "email": "alex.chen@contoso.com", "name": "Alex Chen", "title": "Senior Data Engineer"},
    {"id": "u-002", "email": "maria.garcia@contoso.com", "name": "Maria Garcia", "title": "Analytics Lead"},
    {"id": "u-003", "email": "james.wilson@contoso.com", "name": "James Wilson", "title": "Data Office Manager"},
    {"id": "u-004", "email": "priya.sharma@contoso.com", "name": "Priya Sharma", "title": "ML Engineer"},
    {"id": "u-005", "email": "omar.hassan@contoso.com", "name": "Omar Hassan", "title": "Platform Engineer"},
    {"id": "u-006", "email": "lisa.tanaka@contoso.com", "name": "Lisa Tanaka", "title": "Data Scientist"},
    {"id": "u-007", "email": "raj.patel@contoso.com", "name": "Raj Patel", "title": "BI Developer"},
    {"id": "u-008", "email": "sarah.johnson@contoso.com", "name": "Sarah Johnson", "title": "Data Analyst"},
    {"id": "u-009", "email": "spn-sales-pipeline@contoso.com", "name": "SPN Sales Pipeline", "title": "Service Principal"},
    {"id": "u-010", "email": "david.kim@contoso.com", "name": "David Kim", "title": "Security Engineer"},
]

# Group → user membership (maps entra_group to user indices)
GROUP_MEMBERSHIP = {
    "sg-fabric-de-sales": [0, 4],           # Alex, Omar
    "sg-fabric-analytics-sales": [1, 7],     # Maria, Sarah
    "sg-fabric-do-sales": [2, 7],            # James, Sarah
    "sg-fabric-ml-sales": [3, 5],            # Priya, Lisa
    "sg-fabric-spn-sales": [8],              # SPN
}

# Synthetic resource IDs
WORKSPACE_IDS = {
    "sales-lakehouse": "ws-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "sales-analytics": "ws-b2c3d4e5-f6a7-8901-bcde-f12345678901",
}

DATABRICKS_RESOURCES = {
    "workspace_url": "https://adb-1234567890123456.7.azuredatabricks.net",
    "workspace_id": "1234567890123456",
    "catalogs": {
        "sales_catalog": {"schemas": ["staging", "curated", "raw"]},
        "ml_catalog": {"schemas": ["models", "features", "experiments", "serving"]},
    },
}

EVENT_ACTIONS = ["provision", "revoke", "drift_scan", "recertification"]
DRIFT_CATEGORIES = ["shadow_access", "over_provisioned", "under_provisioned"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stable_id(seed_str: str) -> str:
    """Deterministic short ID from a seed string."""
    return hashlib.sha256(seed_str.encode()).hexdigest()[:12]


def _random_ts(rng: random.Random, days_back: int = 30) -> str:
    """Random ISO timestamp within the last N days."""
    base = datetime(2026, 4, 1, tzinfo=timezone.utc)
    delta = timedelta(
        days=rng.randint(0, days_back),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
        seconds=rng.randint(0, 59),
    )
    return (base - delta).isoformat()


# ---------------------------------------------------------------------------
# Fixture Generators
# ---------------------------------------------------------------------------
def load_packages() -> dict:
    """Load all YAML access packages from the definitions directory."""
    packages = {}
    for f in sorted(PACKAGES_DIR.glob("*.yaml")):
        with open(f) as fh:
            pkg = yaml.safe_load(fh)
        if pkg:
            packages[f.stem] = pkg
    return packages


def generate_access_matrix(packages: dict, rng: random.Random) -> dict:
    """
    Build cross-platform access matrix: principals × resources × platforms.
    Each cell shows the granted permission level.
    """
    rows = []

    for pkg_name, pkg in packages.items():
        pkg_meta = pkg.get("package", {})
        group = pkg_meta.get("entra_group", "")
        members = GROUP_MEMBERSHIP.get(group, [])

        for user_idx in members:
            user = USERS[user_idx]

            # Fabric grants
            grants = pkg.get("grants", {})
            ws_role = grants.get("workspace", {}).get("role", "")
            if ws_role:
                rows.append({
                    "principal": user["email"],
                    "principal_type": "User" if "spn" not in user["email"] else "ServicePrincipal",
                    "platform": "fabric",
                    "resource_type": "workspace",
                    "resource": grants.get("workspace", {}).get("id", "sales-lakehouse"),
                    "permission": ws_role,
                    "package": pkg_meta.get("name", pkg_name),
                    "group": group,
                })

            for item in grants.get("items", []):
                rows.append({
                    "principal": user["email"],
                    "principal_type": "User" if "spn" not in user["email"] else "ServicePrincipal",
                    "platform": "fabric",
                    "resource_type": item.get("type", "Item"),
                    "resource": item.get("name", "unknown"),
                    "permission": ", ".join(item.get("permissions", [])),
                    "package": pkg_meta.get("name", pkg_name),
                    "group": group,
                })

            # Databricks grants
            platforms = pkg.get("platforms", {})
            db = platforms.get("databricks", {})
            if db:
                for uc_grant in db.get("unity_catalog", {}).get("grants", []):
                    rows.append({
                        "principal": user["email"],
                        "principal_type": "User",
                        "platform": "databricks",
                        "resource_type": uc_grant.get("securable_type", ""),
                        "resource": uc_grant.get("securable_name", ""),
                        "permission": ", ".join(uc_grant.get("privileges", [])),
                        "package": pkg_meta.get("name", pkg_name),
                        "group": group,
                    })

                for acl in db.get("workspace_acls", []):
                    rows.append({
                        "principal": user["email"],
                        "principal_type": "User",
                        "platform": "databricks",
                        "resource_type": acl.get("object_type", ""),
                        "resource": acl.get("object_id", ""),
                        "permission": acl.get("permission", ""),
                        "package": pkg_meta.get("name", pkg_name),
                        "group": group,
                    })

    return {
        "generated_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
        "total_entries": len(rows),
        "platforms": sorted({r["platform"] for r in rows}),
        "unique_principals": len({r["principal"] for r in rows}),
        "matrix": rows,
    }


def generate_audit_log(packages: dict, rng: random.Random) -> dict:
    """Generate 30-day audit history with 50+ events across both platforms."""
    events = []
    event_id = 1000

    for pkg_name, pkg in packages.items():
        pkg_meta = pkg.get("package", {})
        group = pkg_meta.get("entra_group", "")
        members = GROUP_MEMBERSHIP.get(group, [])
        has_databricks = "databricks" in pkg.get("platforms", {})
        grants = pkg.get("grants", {})
        db = pkg.get("platforms", {}).get("databricks", {})

        for user_idx in members:
            user = USERS[user_idx]

            # Provision event
            events.append({
                "event_id": f"EVT-{event_id}",
                "timestamp": _random_ts(rng, 25),
                "action": "provision",
                "platform": "fabric",
                "user": user["email"],
                "user_name": user["name"],
                "group": group,
                "package": pkg_meta.get("name", pkg_name),
                "details": f"Workspace role assigned: {pkg.get('grants', {}).get('workspace', {}).get('role', 'Viewer')}",
                "status": "success",
                "initiated_by": "entra-governance",
            })
            event_id += 1

            # Item sharing events
            for item in grants.get("items", []):
                events.append({
                    "event_id": f"EVT-{event_id}",
                    "timestamp": _random_ts(rng, 25),
                    "action": "provision",
                    "platform": "fabric",
                    "user": user["email"],
                    "user_name": user["name"],
                    "group": group,
                    "package": pkg_meta.get("name", pkg_name),
                    "details": f"Shared {item.get('name', 'item')} ({item.get('type', '')}): {', '.join(item.get('permissions', []))}",
                    "status": "success",
                    "initiated_by": "entra-governance",
                })
                event_id += 1

            if has_databricks:
                # UC grant event
                events.append({
                    "event_id": f"EVT-{event_id}",
                    "timestamp": _random_ts(rng, 25),
                    "action": "provision",
                    "platform": "databricks",
                    "user": user["email"],
                    "user_name": user["name"],
                    "group": group,
                    "package": pkg_meta.get("name", pkg_name),
                    "details": "Unity Catalog grants applied",
                    "status": "success",
                    "initiated_by": "entra-governance",
                })
                event_id += 1

                # Workspace ACL event
                events.append({
                    "event_id": f"EVT-{event_id}",
                    "timestamp": _random_ts(rng, 25),
                    "action": "provision",
                    "platform": "databricks",
                    "user": user["email"],
                    "user_name": user["name"],
                    "group": group,
                    "package": pkg_meta.get("name", pkg_name),
                    "details": "Workspace ACLs configured",
                    "status": "success",
                    "initiated_by": "entra-governance",
                })
                event_id += 1

                # Entitlement event
                ents = db.get("entitlements", [])
                if ents:
                    events.append({
                        "event_id": f"EVT-{event_id}",
                        "timestamp": _random_ts(rng, 25),
                        "action": "provision",
                        "platform": "databricks",
                        "user": user["email"],
                        "user_name": user["name"],
                        "group": group,
                        "package": pkg_meta.get("name", pkg_name),
                        "details": f"SCIM entitlements set: {', '.join(ents)}",
                        "status": "success",
                        "initiated_by": "entra-governance",
                    })
                    event_id += 1

    # Add recertification events
    for _ in range(5):
        user = USERS[rng.randint(0, 7)]
        events.append({
            "event_id": f"EVT-{event_id}",
            "timestamp": _random_ts(rng, 10),
            "action": "recertification",
            "platform": rng.choice(["fabric", "databricks"]),
            "user": user["email"],
            "user_name": user["name"],
            "group": rng.choice(list(GROUP_MEMBERSHIP.keys())),
            "package": "periodic-review",
            "details": rng.choice(["Access confirmed", "Access confirmed", "Access revoked — no longer needed"]),
            "status": "success",
            "initiated_by": "access-review-campaign",
        })
        event_id += 1

    # Add drift scan events
    for day_offset in [1, 7, 14, 21, 28]:
        ts = (datetime(2026, 4, 1, 6, 0, 0, tzinfo=timezone.utc) - timedelta(days=day_offset)).isoformat()
        findings_count = rng.randint(0, 4)
        events.append({
            "event_id": f"EVT-{event_id}",
            "timestamp": ts,
            "action": "drift_scan",
            "platform": "all",
            "user": "system",
            "user_name": "Drift Detector",
            "group": "—",
            "package": "—",
            "details": f"Scheduled scan: {findings_count} findings" if findings_count else "Scheduled scan: no drift detected",
            "status": "warning" if findings_count else "success",
            "initiated_by": "timer-trigger",
        })
        event_id += 1

    # Add a few revocation events
    revoke_users = rng.sample(USERS[:8], 3)
    for user in revoke_users:
        events.append({
            "event_id": f"EVT-{event_id}",
            "timestamp": _random_ts(rng, 15),
            "action": "revoke",
            "platform": rng.choice(["fabric", "databricks"]),
            "user": user["email"],
            "user_name": user["name"],
            "group": rng.choice(list(GROUP_MEMBERSHIP.keys())),
            "package": "access-expiration",
            "details": rng.choice(["Access package expired", "Manual removal by admin", "Recertification failure"]),
            "status": "success",
            "initiated_by": rng.choice(["entra-governance", "admin:omar.hassan@contoso.com"]),
        })
        event_id += 1

    # Sort by timestamp descending (most recent first)
    events.sort(key=lambda e: e["timestamp"], reverse=True)

    return {
        "generated_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
        "period_days": 30,
        "total_events": len(events),
        "events_by_action": {
            a: sum(1 for e in events if e["action"] == a)
            for a in EVENT_ACTIONS
        },
        "events_by_platform": {
            p: sum(1 for e in events if e["platform"] == p)
            for p in ["fabric", "databricks", "all"]
        },
        "events": events,
    }


def generate_drift_results(packages: dict, rng: random.Random) -> dict:
    """Generate 8-10 drift findings across Fabric and Databricks."""
    findings = [
        # Fabric findings
        {
            "id": "DRF-001",
            "platform": "fabric",
            "category": "shadow_access",
            "severity": "high",
            "securable": f"workspace:{WORKSPACE_IDS['sales-lakehouse']}",
            "principal": "extern-contractor@partner.com",
            "declared": "—",
            "actual": "Contributor",
            "package": "—",
            "detail": "User has Contributor role but is not in any access package group",
            "detected_at": _random_ts(rng, 1),
        },
        {
            "id": "DRF-002",
            "platform": "fabric",
            "category": "over_provisioned",
            "severity": "high",
            "securable": f"workspace:{WORKSPACE_IDS['sales-lakehouse']}",
            "principal": "sg-fabric-analytics-sales",
            "declared": "Viewer",
            "actual": "Member",
            "package": "analytics-team-sales",
            "detail": "Group has Member role but package declares Viewer",
            "detected_at": _random_ts(rng, 1),
        },
        {
            "id": "DRF-003",
            "platform": "fabric",
            "category": "under_provisioned",
            "severity": "medium",
            "securable": "item:SalesSemanticModel",
            "principal": "sg-fabric-do-sales",
            "declared": "Read",
            "actual": "—",
            "package": "data-office-sales-viewer",
            "detail": "Declared item sharing not found — may need re-provisioning",
            "detected_at": _random_ts(rng, 1),
        },
        # Databricks UC findings
        {
            "id": "DRF-004",
            "platform": "databricks",
            "category": "shadow_access",
            "severity": "high",
            "securable": "catalog:sales_catalog.staging",
            "principal": "temp-intern-group",
            "declared": "—",
            "actual": "SELECT, INSERT",
            "package": "—",
            "detail": "Undeclared group has write access to staging schema",
            "detected_at": _random_ts(rng, 1),
        },
        {
            "id": "DRF-005",
            "platform": "databricks",
            "category": "over_provisioned",
            "severity": "high",
            "securable": "catalog:sales_catalog.curated",
            "principal": "sg-fabric-de-sales",
            "declared": "SELECT",
            "actual": "SELECT, INSERT, MODIFY",
            "package": "databricks-engineer-sales",
            "detail": "Group has write privileges on curated but package only declares SELECT",
            "detected_at": _random_ts(rng, 1),
        },
        {
            "id": "DRF-006",
            "platform": "databricks",
            "category": "under_provisioned",
            "severity": "medium",
            "securable": "catalog:ml_catalog.models",
            "principal": "sg-fabric-ml-sales",
            "declared": "CREATE_MODEL, SELECT",
            "actual": "SELECT",
            "package": "databricks-ml-team-sales",
            "detail": "CREATE_MODEL privilege missing — may need re-grant",
            "detected_at": _random_ts(rng, 1),
        },
        # Workspace ACL findings
        {
            "id": "DRF-007",
            "platform": "databricks",
            "category": "shadow_access",
            "severity": "medium",
            "securable": "workspace_acl:SQLWarehouse/sales-sql-warehouse",
            "principal": "data-platform-admins",
            "declared": "—",
            "actual": "CAN_MANAGE",
            "package": "—",
            "detail": "Admin group has CAN_MANAGE on warehouse but not in any package",
            "detected_at": _random_ts(rng, 1),
        },
        {
            "id": "DRF-008",
            "platform": "databricks",
            "category": "over_provisioned",
            "severity": "medium",
            "securable": "workspace_acl:Notebook/etl-pipelines/",
            "principal": "sg-fabric-ml-sales",
            "declared": "CAN_RUN",
            "actual": "CAN_MANAGE",
            "package": "databricks-ml-team-sales",
            "detail": "Group has CAN_MANAGE but package only grants CAN_RUN",
            "detected_at": _random_ts(rng, 1),
        },
        {
            "id": "DRF-009",
            "platform": "fabric",
            "category": "shadow_access",
            "severity": "low",
            "securable": "sql_endpoint:SELECT on dbo.legacy_reports",
            "principal": "sg-fabric-analytics-sales",
            "declared": "—",
            "actual": "SELECT",
            "package": "—",
            "detail": "SQL grant exists on legacy table not in any package definition",
            "detected_at": _random_ts(rng, 1),
        },
    ]

    return {
        "generated_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
        "scan_timestamp": (datetime(2026, 4, 1, 6, 0, 0, tzinfo=timezone.utc)).isoformat(),
        "total_findings": len(findings),
        "summary": {
            "high": sum(1 for f in findings if f["severity"] == "high"),
            "medium": sum(1 for f in findings if f["severity"] == "medium"),
            "low": sum(1 for f in findings if f["severity"] == "low"),
            "by_platform": {
                "fabric": sum(1 for f in findings if f["platform"] == "fabric"),
                "databricks": sum(1 for f in findings if f["platform"] == "databricks"),
            },
            "by_category": {
                c: sum(1 for f in findings if f["category"] == c)
                for c in DRIFT_CATEGORIES
            },
        },
        "findings": findings,
    }


def generate_provisioning_events(packages: dict, rng: random.Random) -> dict:
    """Generate 3-4 complete provisioning traces showing step-by-step orchestration."""
    traces = []

    # Trace 1: Fabric-only provisioning (data-engineer)
    base_ts = datetime(2026, 3, 28, 14, 32, 10, tzinfo=timezone.utc)
    traces.append({
        "trace_id": "TRC-001",
        "timestamp": base_ts.isoformat(),
        "user": USERS[0],
        "package": "data-engineer-sales-lakehouse",
        "group": "sg-fabric-de-sales",
        "trigger": "entra-governance:group-add",
        "platforms": ["fabric"],
        "duration_ms": 3420,
        "status": "success",
        "steps": [
            {"seq": 1, "ts": base_ts.isoformat(), "platform": "fabric", "layer": "workspace", "action": "assign_role", "target": "sales-lakehouse", "detail": "Assigned Contributor role", "status": "success", "duration_ms": 820},
            {"seq": 2, "ts": (base_ts + timedelta(milliseconds=820)).isoformat(), "platform": "fabric", "layer": "item", "action": "share_item", "target": "SalesMirroredDB", "detail": "Shared with Read, ReadAll, ReadAllApacheSpark", "status": "success", "duration_ms": 650},
            {"seq": 3, "ts": (base_ts + timedelta(milliseconds=1470)).isoformat(), "platform": "fabric", "layer": "item", "action": "share_item", "target": "SalesSemanticModel", "detail": "Shared with Read", "status": "success", "duration_ms": 580},
            {"seq": 4, "ts": (base_ts + timedelta(milliseconds=2050)).isoformat(), "platform": "fabric", "layer": "item", "action": "share_item", "target": "SalesSQLEndpoint", "detail": "Shared with Read, ReadAllSql", "status": "success", "duration_ms": 520},
            {"seq": 5, "ts": (base_ts + timedelta(milliseconds=2570)).isoformat(), "platform": "fabric", "layer": "compute", "action": "sql_grant", "target": "staging schema", "detail": "GRANT SELECT, INSERT, CREATE TABLE ON SCHEMA::staging", "status": "success", "duration_ms": 450},
            {"seq": 6, "ts": (base_ts + timedelta(milliseconds=3020)).isoformat(), "platform": "fabric", "layer": "compute", "action": "sql_deny", "target": "curated schema", "detail": "DENY DELETE ON SCHEMA::curated", "status": "success", "duration_ms": 400},
        ],
    })

    # Trace 2: Databricks provisioning (databricks-engineer)
    base_ts2 = datetime(2026, 3, 30, 9, 15, 0, tzinfo=timezone.utc)
    traces.append({
        "trace_id": "TRC-002",
        "timestamp": base_ts2.isoformat(),
        "user": USERS[0],
        "package": "databricks-engineer-sales",
        "group": "sg-fabric-de-sales",
        "trigger": "entra-governance:group-add",
        "platforms": ["fabric", "databricks"],
        "duration_ms": 5840,
        "status": "success",
        "steps": [
            {"seq": 1, "ts": base_ts2.isoformat(), "platform": "fabric", "layer": "workspace", "action": "assign_role", "target": "sales-lakehouse", "detail": "Assigned Contributor role", "status": "success", "duration_ms": 780},
            {"seq": 2, "ts": (base_ts2 + timedelta(milliseconds=780)).isoformat(), "platform": "databricks", "layer": "entitlements", "action": "set_entitlements", "target": "sg-fabric-de-sales", "detail": "Set workspace-access, databricks-sql-access", "status": "success", "duration_ms": 620},
            {"seq": 3, "ts": (base_ts2 + timedelta(milliseconds=1400)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "sales_catalog", "detail": "GRANT USE_CATALOG ON CATALOG sales_catalog", "status": "success", "duration_ms": 540},
            {"seq": 4, "ts": (base_ts2 + timedelta(milliseconds=1940)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "sales_catalog.staging", "detail": "GRANT USE_SCHEMA, SELECT, INSERT, CREATE_TABLE ON SCHEMA staging", "status": "success", "duration_ms": 680},
            {"seq": 5, "ts": (base_ts2 + timedelta(milliseconds=2620)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "sales_catalog.curated", "detail": "GRANT USE_SCHEMA, SELECT ON SCHEMA curated", "status": "success", "duration_ms": 520},
            {"seq": 6, "ts": (base_ts2 + timedelta(milliseconds=3140)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "sales_catalog.raw", "detail": "GRANT USE_SCHEMA, SELECT ON SCHEMA raw", "status": "success", "duration_ms": 490},
            {"seq": 7, "ts": (base_ts2 + timedelta(milliseconds=3630)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "ClusterPolicy/de-standard-policy", "detail": "Set CAN_USE", "status": "success", "duration_ms": 580},
            {"seq": 8, "ts": (base_ts2 + timedelta(milliseconds=4210)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "SQLWarehouse/sales-sql-warehouse", "detail": "Set CAN_USE", "status": "success", "duration_ms": 520},
            {"seq": 9, "ts": (base_ts2 + timedelta(milliseconds=4730)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "Notebook/etl-pipelines/", "detail": "Set CAN_EDIT", "status": "success", "duration_ms": 560},
            {"seq": 10, "ts": (base_ts2 + timedelta(milliseconds=5290)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "Repo/sales-repo", "detail": "Set CAN_EDIT", "status": "success", "duration_ms": 550},
        ],
    })

    # Trace 3: ML team provisioning (databricks-ml-team)
    base_ts3 = datetime(2026, 3, 31, 11, 45, 0, tzinfo=timezone.utc)
    traces.append({
        "trace_id": "TRC-003",
        "timestamp": base_ts3.isoformat(),
        "user": USERS[3],
        "package": "databricks-ml-team-sales",
        "group": "sg-fabric-ml-sales",
        "trigger": "entra-governance:group-add",
        "platforms": ["fabric", "databricks"],
        "duration_ms": 7120,
        "status": "success",
        "steps": [
            {"seq": 1, "ts": base_ts3.isoformat(), "platform": "fabric", "layer": "workspace", "action": "assign_role", "target": "sales-lakehouse", "detail": "Assigned Contributor role", "status": "success", "duration_ms": 810},
            {"seq": 2, "ts": (base_ts3 + timedelta(milliseconds=810)).isoformat(), "platform": "databricks", "layer": "entitlements", "action": "set_entitlements", "target": "sg-fabric-ml-sales", "detail": "Set workspace-access, databricks-sql-access, allow-cluster-create", "status": "success", "duration_ms": 650},
            {"seq": 3, "ts": (base_ts3 + timedelta(milliseconds=1460)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "sales_catalog.curated", "detail": "GRANT USE_SCHEMA, SELECT ON SCHEMA curated", "status": "success", "duration_ms": 580},
            {"seq": 4, "ts": (base_ts3 + timedelta(milliseconds=2040)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "ml_catalog", "detail": "GRANT USE_CATALOG ON CATALOG ml_catalog", "status": "success", "duration_ms": 520},
            {"seq": 5, "ts": (base_ts3 + timedelta(milliseconds=2560)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "ml_catalog.models", "detail": "GRANT USE_SCHEMA, CREATE_MODEL, SELECT ON SCHEMA models", "status": "success", "duration_ms": 610},
            {"seq": 6, "ts": (base_ts3 + timedelta(milliseconds=3170)).isoformat(), "platform": "databricks", "layer": "unity_catalog", "action": "grant", "target": "ml_catalog.features", "detail": "GRANT USE_SCHEMA, CREATE_TABLE, CREATE_FUNCTION, SELECT ON SCHEMA features", "status": "success", "duration_ms": 590},
            {"seq": 7, "ts": (base_ts3 + timedelta(milliseconds=3760)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "ServingEndpoint/sales-serving", "detail": "Set CAN_MANAGE", "status": "success", "duration_ms": 680},
            {"seq": 8, "ts": (base_ts3 + timedelta(milliseconds=4440)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "DLTPipeline/feature-pipeline", "detail": "Set CAN_RUN", "status": "success", "duration_ms": 620},
            {"seq": 9, "ts": (base_ts3 + timedelta(milliseconds=5060)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "Job/ml-training-daily", "detail": "Set CAN_MANAGE_RUN", "status": "success", "duration_ms": 580},
            {"seq": 10, "ts": (base_ts3 + timedelta(milliseconds=5640)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "Experiment/sales-forecasting", "detail": "Set CAN_EDIT", "status": "success", "duration_ms": 540},
            {"seq": 11, "ts": (base_ts3 + timedelta(milliseconds=6180)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "Notebook/ml-notebooks/", "detail": "Set CAN_EDIT", "status": "success", "duration_ms": 480},
            {"seq": 12, "ts": (base_ts3 + timedelta(milliseconds=6660)).isoformat(), "platform": "databricks", "layer": "workspace_acl", "action": "set_permission", "target": "Repo/ml-repo", "detail": "Set CAN_EDIT", "status": "success", "duration_ms": 460},
        ],
    })

    # Trace 4: Partial failure — revocation with one step failing
    base_ts4 = datetime(2026, 3, 29, 16, 20, 0, tzinfo=timezone.utc)
    traces.append({
        "trace_id": "TRC-004",
        "timestamp": base_ts4.isoformat(),
        "user": USERS[7],
        "package": "analytics-team-sales",
        "group": "sg-fabric-analytics-sales",
        "trigger": "entra-governance:access-expiration",
        "platforms": ["fabric"],
        "duration_ms": 2180,
        "status": "partial",
        "steps": [
            {"seq": 1, "ts": base_ts4.isoformat(), "platform": "fabric", "layer": "workspace", "action": "remove_role", "target": "sales-analytics", "detail": "Removed Viewer role", "status": "success", "duration_ms": 720},
            {"seq": 2, "ts": (base_ts4 + timedelta(milliseconds=720)).isoformat(), "platform": "fabric", "layer": "item", "action": "revoke_item", "target": "SalesMirroredDB", "detail": "Item revocation queued for manual review", "status": "success", "duration_ms": 380},
            {"seq": 3, "ts": (base_ts4 + timedelta(milliseconds=1100)).isoformat(), "platform": "fabric", "layer": "compute", "action": "sql_revoke", "target": "analytics schema", "detail": "REVOKE SELECT ON SCHEMA::analytics — connection timeout", "status": "failed", "duration_ms": 1080},
        ],
    })

    return {
        "generated_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
        "total_traces": len(traces),
        "traces_by_status": {
            "success": sum(1 for t in traces if t["status"] == "success"),
            "partial": sum(1 for t in traces if t["status"] == "partial"),
            "failed": sum(1 for t in traces if t["status"] == "failed"),
        },
        "traces": traces,
    }


def generate_platform_summary(packages: dict, rng: random.Random) -> dict:
    """Generate platform status and statistics."""
    fabric_pkgs = [p for p in packages.values() if p.get("grants", {}).get("workspace")]
    databricks_pkgs = [p for p in packages.values() if p.get("platforms", {}).get("databricks")]

    return {
        "generated_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
        "platforms": [
            {
                "name": "Microsoft Fabric",
                "id": "fabric",
                "status": "active",
                "version": "GA",
                "icon": "fabric",
                "stats": {
                    "access_packages": len(fabric_pkgs),
                    "active_users": len({
                        idx for pkg in fabric_pkgs
                        for idx in GROUP_MEMBERSHIP.get(pkg.get("package", {}).get("entra_group", ""), [])
                    }),
                    "workspaces_managed": len(WORKSPACE_IDS),
                    "items_shared": 12,
                    "sql_grants_active": 18,
                    "last_provision": "2026-03-31T14:32:10Z",
                    "last_drift_scan": "2026-04-01T06:00:00Z",
                    "drift_findings": 4,
                },
                "capabilities": [
                    "Workspace role assignment",
                    "Item-level sharing (Read, Build, Reshare)",
                    "SQL analytics endpoint GRANT/DENY",
                    "OneLake security roles",
                    "Row-level & object-level security",
                ],
            },
            {
                "name": "Azure Databricks",
                "id": "databricks",
                "status": "active",
                "version": "Unity Catalog",
                "icon": "databricks",
                "stats": {
                    "access_packages": len(databricks_pkgs),
                    "active_users": len({
                        idx for pkg in databricks_pkgs
                        for idx in GROUP_MEMBERSHIP.get(pkg.get("package", {}).get("entra_group", ""), [])
                    }),
                    "catalogs_managed": len(DATABRICKS_RESOURCES["catalogs"]),
                    "uc_grants_active": 24,
                    "workspace_acls_active": 16,
                    "scim_groups_synced": 3,
                    "last_provision": "2026-03-31T11:45:00Z",
                    "last_drift_scan": "2026-04-01T06:00:00Z",
                    "drift_findings": 5,
                },
                "capabilities": [
                    "Unity Catalog grants (CATALOG, SCHEMA, TABLE, VIEW, VOLUME, MODEL, FUNCTION)",
                    "Workspace ACLs (16 object types)",
                    "SCIM entitlements (workspace-access, sql-access, cluster-create, instance-pool)",
                    "Compute policy assignment",
                    "System table drift detection",
                ],
            },
            {
                "name": "Snowflake",
                "id": "snowflake",
                "status": "coming_soon",
                "version": "—",
                "icon": "snowflake",
                "stats": {
                    "access_packages": 0,
                    "active_users": 0,
                },
                "capabilities": [
                    "Database/schema/table GRANT/REVOKE",
                    "Role hierarchy management",
                    "Warehouse access control",
                    "Row access policies",
                    "Dynamic data masking",
                ],
                "eta": "Phase 3 — Q3 2026",
            },
        ],
        "totals": {
            "platforms_active": 2,
            "platforms_planned": 1,
            "total_access_packages": len(packages),
            "total_active_users": len({
                idx
                for pkg in packages.values()
                for idx in GROUP_MEMBERSHIP.get(pkg.get("package", {}).get("entra_group", ""), [])
            }),
            "total_entra_groups": len(GROUP_MEMBERSHIP),
        },
    }


def generate_system_table_samples(packages: dict, rng: random.Random) -> dict:
    """
    Generate synthetic Databricks system table samples:
    - information_schema.table_privileges
    - system.access.audit
    - system.billing.usage
    """
    # table_privileges — simulates system.information_schema.table_privileges
    table_privileges = []
    for schema in ["staging", "curated", "raw"]:
        for principal in ["sg-fabric-de-sales", "sg-fabric-ml-sales", "sg-fabric-analytics-sales"]:
            privs = ["SELECT"]
            if schema == "staging" and principal == "sg-fabric-de-sales":
                privs = ["SELECT", "INSERT", "CREATE_TABLE", "MODIFY"]
            elif schema == "curated" and principal == "sg-fabric-ml-sales":
                privs = ["SELECT"]

            for priv in privs:
                table_privileges.append({
                    "catalog_name": "sales_catalog",
                    "schema_name": schema,
                    "table_name": "*",
                    "grantee": principal,
                    "privilege_type": priv,
                    "is_grantable": "NO",
                    "inherited_from": f"SCHEMA `sales_catalog`.`{schema}`",
                })

    # ML catalog privileges
    for schema, privs_map in [
        ("models", {"sg-fabric-ml-sales": ["SELECT", "CREATE_MODEL"]}),
        ("features", {"sg-fabric-ml-sales": ["SELECT", "CREATE_TABLE", "CREATE_FUNCTION"]}),
        ("serving", {"sg-fabric-ml-sales": ["SELECT", "CREATE_FUNCTION"]}),
    ]:
        for principal, privs in privs_map.items():
            for priv in privs:
                table_privileges.append({
                    "catalog_name": "ml_catalog",
                    "schema_name": schema,
                    "table_name": "*",
                    "grantee": principal,
                    "privilege_type": priv,
                    "is_grantable": "NO",
                    "inherited_from": f"SCHEMA `ml_catalog`.`{schema}`",
                })

    # access.audit — simulates system.access.audit
    audit_log = []
    actions_pool = [
        ("getTable", "unityCatalog"),
        ("getSchema", "unityCatalog"),
        ("createTable", "unityCatalog"),
        ("generateTemporaryTableCredential", "unityCatalog"),
        ("getPermissions", "unityCatalog"),
        ("updatePermissions", "unityCatalog"),
        ("getWarehouse", "databrickssql"),
        ("executeStatement", "databrickssql"),
        ("clusterPolicyAccess", "clusters"),
    ]
    for _ in range(25):
        user = USERS[rng.randint(0, 5)]
        action, service = rng.choice(actions_pool)
        base_time = datetime(2026, 3, 31, tzinfo=timezone.utc) + timedelta(
            hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        audit_log.append({
            "event_time": base_time.isoformat(),
            "event_date": base_time.strftime("%Y-%m-%d"),
            "service_name": service,
            "action_name": action,
            "user_identity": {"email": user["email"]},
            "request_params": {"catalog_name": rng.choice(["sales_catalog", "ml_catalog"])},
            "response": {"status_code": 200},
            "source_ip_address": f"10.0.{rng.randint(1,10)}.{rng.randint(1,254)}",
            "workspace_id": DATABRICKS_RESOURCES["workspace_id"],
        })

    # billing.usage — simulates system.billing.usage
    billing_usage = []
    skus = [
        ("STANDARD_ALL_PURPOSE_COMPUTE", 0.40),
        ("STANDARD_SQL_COMPUTE", 0.22),
        ("STANDARD_SERVERLESS_SQL_COMPUTE", 0.35),
        ("STANDARD_JOBS_COMPUTE", 0.15),
        ("STANDARD_ML_COMPUTE", 0.65),
    ]
    for day_offset in range(7):
        day = datetime(2026, 3, 25, tzinfo=timezone.utc) + timedelta(days=day_offset)
        for sku_name, rate in skus:
            dbu_count = round(rng.uniform(5, 80), 2)
            billing_usage.append({
                "usage_date": day.strftime("%Y-%m-%d"),
                "workspace_id": DATABRICKS_RESOURCES["workspace_id"],
                "sku_name": sku_name,
                "usage_quantity": dbu_count,
                "usage_unit": "DBU",
                "estimated_cost_usd": round(dbu_count * rate, 2),
                "billing_origin_product": "DATABRICKS_SQL" if "SQL" in sku_name else "DEFAULT",
                "usage_type": "INTERACTIVE" if "ALL_PURPOSE" in sku_name else "AUTOMATED",
            })

    return {
        "generated_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
        "system_tables": {
            "information_schema.table_privileges": {
                "description": "Unity Catalog table-level privilege assignments",
                "row_count": len(table_privileges),
                "sample_rows": table_privileges,
            },
            "access.audit": {
                "description": "Databricks audit log events (last 24h sample)",
                "row_count": len(audit_log),
                "sample_rows": sorted(audit_log, key=lambda r: r["event_time"], reverse=True),
            },
            "billing.usage": {
                "description": "Databricks DBU consumption (7-day window)",
                "row_count": len(billing_usage),
                "sample_rows": billing_usage,
            },
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate demo fixture data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading access packages from {PACKAGES_DIR}...")
    packages = load_packages()
    print(f"  Found {len(packages)} packages: {', '.join(packages.keys())}")

    generators = {
        "access-matrix.json": generate_access_matrix,
        "audit-log.json": generate_audit_log,
        "drift-results.json": generate_drift_results,
        "provisioning-events.json": generate_provisioning_events,
        "platform-summary.json": generate_platform_summary,
        "system-table-samples.json": generate_system_table_samples,
    }

    for filename, gen_func in generators.items():
        filepath = out / filename
        data = gen_func(packages, rng)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  Generated {filename} ({len(json.dumps(data)):,} bytes)")

    print(f"\nDone! {len(generators)} fixture files written to {out}")


if __name__ == "__main__":
    main()
