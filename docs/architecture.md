# Architecture Deep Dive

## Overview

The Fabric Access Platform solves a fundamental gap in Microsoft Fabric's permission management: there is no native way to define reusable, persona-based access packages that bundle workspace roles, item-level permissions, and compute-level security grants into a single, auditable, automatable unit.

This document explains the technical architecture, the design decisions behind it, and how each component fits together.

## The Permission Gap

Fabric's permission model operates across three independent layers, each with its own management surface:

```
┌──────────────────────────────────────────────────────┐
│ Layer 1: Entra Authentication                        │
│ Identity verification, MFA, Conditional Access       │
│ Management: Azure Portal / Entra Admin Center        │
├──────────────────────────────────────────────────────┤
│ Layer 2: Fabric Access                               │
│ Workspace roles (Admin/Member/Contributor/Viewer)    │
│ Item permissions (Read/ReadAll/Reshare/Write/Execute)│
│ Management: Fabric Portal UI + limited REST APIs     │
├──────────────────────────────────────────────────────┤
│ Layer 3: Compute Security                            │
│ SQL endpoint (T-SQL GRANT/REVOKE/DENY)               │
│ Semantic model (DAX RLS/OLS)                         │
│ OneLake security (custom table/folder roles)         │
│ Management: T-SQL, XMLA, Fabric Portal               │
└──────────────────────────────────────────────────────┘
```

The critical gaps at enterprise scale are:

1. **No cross-layer bundling** — Granting a "Data Engineer" access level requires separate actions across workspace roles, item sharing, SQL endpoint grants, and OneLake security roles. These are disconnected.

2. **No programmatic item sharing** — The Fabric REST API's `resolvePermissions` endpoint is read-only. Granting item-level permissions programmatically requires falling back to the Power BI REST API's sharing endpoints or undocumented internal APIs.

3. **No access lifecycle** — No native request, approval, time-boxing, or recertification workflow exists within Fabric. Entra ID Governance provides this for group membership but has no awareness of Fabric-specific permissions.

## Architecture Layers

### Request Layer — Entra ID Governance

Entra ID Governance (P2 license) provides the identity lifecycle that Fabric lacks:

**Access Packages** define bundles of resources a user can request. In our framework, each access package maps 1:1 to a YAML definition file and an Entra security group. When a user's request is approved, they are added to the security group — which triggers the automation layer.

**Approval Policies** enforce multi-stage approval flows. The YAML `approval_policy` field maps to Entra policies:
- `manager-only` — Direct manager approves
- `manager-plus-platform` — Manager approves, then platform team approves
- `platform-team-only` — Used for service accounts (no manager chain)
- `auto-approve` — For low-sensitivity packages (use sparingly)

**Lifecycle Policies** handle expiration and recertification:
- `expiration_days` in the YAML sets the access duration
- Entra automatically removes expired users from the security group
- Group removal triggers the revocation Azure Function

### Automation Layer — Azure Functions + Configuration Library

This is the custom glue that translates Entra group membership events into Fabric permission provisioning.

#### Configuration Library

Access package definitions live as YAML files in `access-packages/definitions/`. This is deliberate — YAML files in Git provide:

- **Version control** — Every change is tracked, attributed, and reversible
- **PR-based review** — Permission changes require code review before merge
- **CI validation** — The `validate_packages.py` script runs on every PR, catching schema violations, permission escalations, and stale review dates
- **Audit trail** — Git log serves as an immutable record of who changed what access package and when
- **Declarative state** — The YAML files are the single source of truth; drift detection compares them against Fabric's actual state

Each YAML file declares the complete permission surface for a persona:

```yaml
grants:
  workspace:
    role: Contributor            # Layer 2: Fabric workspace role
  items:
    - type: MirroredDatabase
      permissions: [Read, ReadAll] # Layer 2: Item-level sharing
  compute:
    sql_endpoint:
      grants:
        - GRANT SELECT ON SCHEMA::staging  # Layer 3: Compute security
    onelake:
      security_role: de-read-tables        # Layer 3: OneLake security
```

#### Provisioning Functions

Azure Functions execute the multi-layer permission provisioning. The choice of Functions over Logic Apps is deliberate:

- **Imperative control** — Provisioning across 3 layers requires conditional logic, error handling, and retry patterns that are awkward in declarative Logic Apps connectors
- **API client reuse** — The `fabric_client.py` module wraps both Fabric REST API and Power BI REST API, handling token management, rate limiting, and pagination
- **Testability** — Python functions with dependency injection are straightforward to unit test

The provisioning flow for a single access package grant:

```
1. Load YAML config for the triggered group
2. Resolve workspace ID from environment variable
3. Assign workspace role via Power BI REST API
   POST /v1.0/myorg/groups/{workspaceId}/users
4. For each item in the package:
   a. Find item by name in workspace
   b. Share item via Power BI REST API
5. Generate T-SQL scripts from compute config
6. Execute scripts against SQL analytics endpoint via pyodbc
7. Log all results to Azure Monitor
```

#### Drift Detection

The drift detector runs on a daily schedule and compares:
- **Declared state** (YAML configs) against **actual state** (Fabric API responses)
- Identifies shadow access (users with permissions not in any package)
- Identifies under-provisioning (declared permissions missing in Fabric)
- Identifies over-provisioning (actual permissions exceed declarations)

Drift findings are classified by severity:
- **High** — Over-provisioned access (security risk)
- **Medium** — Under-provisioned access (operational gap)
- **Low** — Stale metadata or cosmetic discrepancies

### Fabric Layer — Where Permissions Are Enforced

This layer is the target of the automation. Permissions are enforced by Fabric's runtime engines:

**Workspace Roles** — Managed via the Power BI REST API `groups/{id}/users` endpoint. Supports User, Group, and ServicePrincipal types. The Terraform provider handles this declaratively for infrastructure-as-code flows; Azure Functions handle it for dynamic, event-driven provisioning.

**Item Permissions** — Managed via item sharing. When you share a mirrored database, Fabric automatically cascades access to the SQL analytics endpoint and default semantic model. This is a key architectural advantage — one share call provisions access to three related items.

**SQL Endpoint Security** — Managed via standard T-SQL GRANT/REVOKE/DENY statements executed through pyodbc. Supports schema-level, table-level, and row-level security. The `sql_grants.py` module generates idempotent scripts from the YAML compute config.

**OneLake Security** — Custom roles that grant read access to specific tables and folders. Managed via Fabric REST API.

## Terraform vs. Azure Functions — Separation of Concerns

A common question: why not do everything in Terraform or everything in Azure Functions?

| Concern | Terraform | Azure Functions |
|---------|-----------|----------------|
| Workspace provisioning | Yes | No |
| Capacity management | Yes | No |
| Entra security groups | Yes | No |
| Git integration | Yes | No |
| Workspace role assignments (static) | Yes | No |
| Dynamic user provisioning (event-driven) | No | Yes |
| Item-level sharing | No | Yes |
| SQL GRANT/REVOKE | No | Yes |
| Drift detection | No | Yes |

Terraform manages the **infrastructure** — things that are provisioned once and change infrequently (workspaces, capacities, security groups, static role assignments). Azure Functions manage the **operations** — things that change dynamically based on user requests (individual access grants, revocations, audit events).

As the Terraform Provider for Fabric matures, some operations currently handled by Functions (like item-level sharing) may migrate to Terraform resources. The YAML config layer provides an abstraction that insulates the provisioning logic from the specific API surface used.

## Security Considerations

**Service Principal Permissions** — The automation SPN requires:
- Power BI Service API: `Workspace.ReadWrite.All`, `Item.ReadWrite.All`
- Microsoft Graph: `GroupMember.Read.All`, `User.Read.All`
- Fabric Admin Portal: "Service principals can use Fabric APIs" enabled
- Workspace membership: At least Contributor role in target workspaces

**Least Privilege** — The SPN should only be added to workspaces managed by this platform. Use a dedicated Entra security group for the SPN and scope Fabric admin settings to that group.

**Secret Management** — Client secrets are stored in GitHub Secrets for CI/CD and Azure Function App Settings (backed by Key Vault in production). The bootstrap script generates a 1-year secret; rotate before expiry.

**Token Bootstrap** — New service principals must make an initial API call to bootstrap their Fabric security token. Until this is done, API calls will fail with permission errors even if the SPN has correct workspace roles.

## Monitoring and Observability

All provisioning events are structured as JSON and logged to Azure Monitor. The control plane UI reads from Log Analytics to provide:

- Real-time provisioning status
- Historical audit trail
- Drift detection reports
- Permission utilization metrics

Custom Kusto queries in Log Analytics enable alerting on:
- Failed provisioning attempts
- High-severity drift findings
- Unusual access patterns (e.g., sudden spike in access requests)
