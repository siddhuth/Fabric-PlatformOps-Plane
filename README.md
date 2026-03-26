# Fabric Access Platform

A platform operations framework for automating Microsoft Fabric item-level permission management at enterprise scale.

## Problem

Fabric's native permission model works for small teams but breaks at enterprise scale:

- **No Access Packages** — No native concept of bundled permission sets mapped to personas
- **Limited Write APIs** — Fabric REST API can resolve permissions but has limited official support for granting them programmatically
- **No Request Workflow** — No built-in self-service request → approval → provisioning lifecycle
- **Manual Sharing** — Item permissions assigned through UI clicks with no audit trail or repeatability

## Solution Architecture

This framework layers **Entra ID Governance** (request lifecycle) + **Custom Automation** (Azure Functions) + **Terraform** (infrastructure-as-code) to deliver a scalable, auditable, Git-driven access management control plane.

```
┌─────────────────────────────────────────────────────────┐
│  REQUEST LAYER — Entra ID Governance                    │
│  Access Packages · Approval Workflows · Lifecycle       │
└──────────────────────────┬──────────────────────────────┘
                           │ Group membership event
                           ▼
┌─────────────────────────────────────────────────────────┐
│  AUTOMATION LAYER — Azure Functions + Config Library    │
│  YAML Definitions · Provisioning Functions · API Client │
└──────────────────────────┬──────────────────────────────┘
                           │ Multi-layer permission grants
                           ▼
┌─────────────────────────────────────────────────────────┐
│  FABRIC LAYER — Workspace Roles, Items, Compute         │
│  Workspace Roles · Item Sharing · T-SQL · OneLake       │
└─────────────────────────────────────────────────────────┘
```

## Repository Structure

```
fabric-access-platform/
├── terraform/
│   ├── modules/workspace/          # Workspace + role assignment modules
│   ├── modules/entra-groups/       # Security group + access package setup
│   ├── modules/capacity/           # Fabric capacity provisioning
│   └── environments/               # dev / staging / prod tfvars
├── access-packages/
│   ├── definitions/                # YAML persona → permission mappings
│   │   ├── data-engineer.yaml
│   │   ├── data-office.yaml
│   │   ├── analytics-team.yaml
│   │   └── service-account.yaml
│   └── schemas/                    # JSON Schema for package validation
├── functions/
│   ├── provision-access/           # Triggered by Entra group change events
│   ├── revoke-access/              # Triggered by removal / expiration
│   ├── drift-detector/             # Scheduled scan: config vs actual state
│   └── shared/
│       ├── fabric_client.py        # Wrapper around Fabric + PBI REST APIs
│       └── sql_grants.py           # T-SQL GRANT/REVOKE generator
├── control-plane-ui/               # React app for platform team dashboard
│   └── src/views/
│       ├── audit-log/
│       ├── access-matrix/
│       └── override-panel/
├── scripts/
│   ├── bootstrap.sh                # Initial Entra app registration + perms
│   └── validate_packages.py        # CI check for access package configs
├── .github/workflows/
│   ├── terraform-plan.yml
│   ├── deploy-functions.yml
│   └── validate-access-packages.yml
└── docs/
    ├── architecture.md
    └── runbook.md
```

## Persona Access Packages

Each persona maps to a YAML-defined access package that bundles workspace role, item permissions, and compute-level grants:

| Persona | Workspace Role | Item Permissions | Compute-Level Grants |
|---------|---------------|-----------------|---------------------|
| Data Engineer | Contributor | Read, ReadAll | SQL: SELECT+INSERT on staging, OneLake: Read /Tables/* |
| Data Office / Steward | Viewer | Read (view only) | SQL: SELECT on curated views, Semantic Model: RLS |
| Analytics Team | Viewer | Read, Build | Semantic Model: Read+Build, SQL: SELECT analytics |
| Service Account (SPN) | Contributor | Read, ReadAll, Execute | SQL: db_datareader, OneLake: ReadAll |

## End-to-End Flow

1. **User requests access** via Entra ID My Access portal, selecting a persona package
2. **Approval workflow** runs (manager + platform team approval chain)
3. **Group membership updated** — user added to Entra security group
4. **Event fires webhook** — Microsoft Graph subscription triggers Azure Function
5. **Function reads YAML config** and orchestrates multi-layer permission grants
6. **Permissions propagated** across workspace roles, item sharing, SQL grants, OneLake roles
7. **Audit event logged** to Log Analytics; scheduled drift detector validates state

## Prerequisites

- Azure subscription with Fabric capacity provisioned
- Entra ID P2 license (for Access Packages / Identity Governance)
- Terraform >= 1.8, < 2.0
- Python 3.11+ (Azure Functions runtime)
- Node.js 18+ (control plane UI)
- Azure CLI authenticated with sufficient privileges

## Quick Start

```bash
# 1. Bootstrap Entra app registration and permissions
./scripts/bootstrap.sh

# 2. Initialize and apply Terraform
cd terraform/environments/dev
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 3. Deploy Azure Functions
func azure functionapp publish <your-function-app-name>

# 4. Validate access package configs
python scripts/validate_packages.py
```

## Phased Implementation

| Phase | Timeline | Deliverables |
|-------|----------|-------------|
| **Foundation** | Weeks 1-4 | YAML definitions, Entra groups, Terraform modules, workspace deployment |
| **Automation** | Weeks 5-8 | Azure Functions, API client library, event wiring, SQL grant scripts |
| **Control Plane** | Weeks 9-12 | Platform dashboard, Entra Access Packages integration, audit logging, drift reconciliation |

## Documentation

- [Architecture Deep Dive](docs/architecture.md) — Detailed technical architecture and design decisions
- [Operations Runbook](docs/runbook.md) — Day-to-day operational procedures and troubleshooting

## License

MIT
