# Fabric Access Platform

A multi-platform access control plane for **Microsoft Fabric**, **Azure Databricks** (Unity Catalog), and **Snowflake** (planned). Automates persona-based permission management at enterprise scale through Git-driven YAML definitions, event-driven provisioning, and a stakeholder-facing demo dashboard.

## Problem

Enterprise data platforms lack native, cross-platform access packages that bundle permissions across multiple layers (workspace roles, item-level sharing, compute-level security grants) into a single, auditable, Git-driven unit.

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  REQUEST LAYER — Entra ID Governance                                    │
│  Access Packages · Approval Workflows · Lifecycle Policies              │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ Group membership event
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PROVIDER REGISTRY — Platform-Aware Dispatch                            │
│  ┌──────────────────┐ ┌────────────────────┐ ┌────────────────────────┐ │
│  │  FabricProvider   │ │ DatabricksProvider │ │ SnowflakeProvider      │ │
│  │  fabric_client.py │ │ databricks_client  │ │ (stub — Phase 3)      │ │
│  │  sql_grants.py    │ │ uc_grants.py       │ │                       │ │
│  └──────────────────┘ └────────────────────┘ └────────────────────────┘ │
│  MockProvider (DEMO_MODE=true) — fixture-driven, no cloud credentials   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌───────────────┐  ┌──────────────┐
   │   FABRIC     │  │  DATABRICKS   │  │  SNOWFLAKE   │
   │  Workspace   │  │  Workspace    │  │  (Phase 3)   │
   │  Items       │  │  Unity Catalog│  │              │
   │  SQL / Lake  │  │  Compute ACLs │  │              │
   └─────────────┘  └───────────────┘  └──────────────┘
```

## Quick Start — Run the Demo

The demo dashboard runs entirely from fixture data with no cloud credentials required.

```bash
# 1. Install UI dependencies
cd control-plane-ui
npm install

# 2. Start the dev server
npm run dev
```

Open `http://localhost:5173` to explore:

| Page | Route | What you'll see |
|------|-------|-----------------|
| **Platform Overview** | `/` | Fabric, Databricks, Snowflake cards with live stats |
| **Access Matrix** | `/access-matrix` | Principal x resource grid — click any cell for grant detail |
| **Provisioning Flow** | `/provisioning` | Animated step-by-step trace replay across platforms |
| **Audit Log** | `/audit-log` | 55 events over 30 days with platform-colored timeline |
| **Drift Dashboard** | `/drift` | 9 findings with expected-vs-actual diff display |

### Regenerate Fixture Data

If you modify access package YAML definitions, regenerate the demo data:

```bash
python demo/generate_fixtures.py --seed 42
```

### Build for Deployment

```bash
cd control-plane-ui
npm run build     # Output in dist/ — deploy to any static host
```

## Repository Structure

```
fabric-access-platform/
├── access-packages/
│   ├── definitions/                # YAML persona → permission mappings
│   │   ├── data-engineer.yaml          # Fabric-only
│   │   ├── data-office.yaml            # Fabric-only
│   │   ├── analytics-team.yaml         # Fabric-only
│   │   ├── service-account.yaml        # Fabric-only
│   │   ├── databricks-engineer.yaml    # Multi-platform (Fabric + Databricks)
│   │   └── databricks-ml-team.yaml     # Multi-platform (Fabric + Databricks)
│   └── schemas/
│       └── access-package.schema.json  # JSON Schema v7 (Fabric + Databricks + Snowflake)
├── functions/
│   ├── provision-access/           # Azure Function: Entra group-add → multi-platform provision
│   ├── revoke-access/              # Azure Function: group-remove → revocation
│   ├── drift-detector/             # Azure Function: scheduled drift scan
│   └── shared/
│       ├── provider_registry.py        # PlatformProvider ABC + factory
│       ├── fabric_client.py            # Fabric REST + Power BI API wrapper
│       ├── databricks_client.py        # Databricks OAuth M2M + workspace ACLs
│       ├── databricks_uc_grants.py     # Unity Catalog SQL GRANT/REVOKE
│       ├── mock_providers.py           # Demo mode implementations
│       └── sql_grants.py               # T-SQL GRANT/REVOKE generator
├── terraform/
│   ├── modules/
│   │   ├── workspace/              # Fabric workspace provisioning
│   │   ├── capacity/               # Fabric capacity provisioning
│   │   ├── entra-groups/           # Entra security groups
│   │   ├── databricks-workspace/   # Azure Databricks workspace + metastore
│   │   ├── databricks-uc-catalog/  # Unity Catalog (catalogs, schemas, tables)
│   │   └── databricks-scim/        # SCIM group sync + entitlements
│   └── environments/
│       └── dev/terraform.tfvars
├── control-plane-ui/               # React 18 + TypeScript + Vite + Tailwind
│   └── src/
│       ├── pages/                      # 5 navigable pages
│       ├── components/                 # Reusable UI components
│       ├── hooks/                      # Fixture data loading hooks
│       └── lib/                        # Platform colors and utilities
├── demo/
│   ├── generate_fixtures.py        # Reads YAMLs → produces fixture JSONs
│   └── fixtures/                   # 6 fixture files for the UI demo
├── scripts/
│   ├── bootstrap.sh                # One-time Entra app registration + permissions
│   └── validate_packages.py       # CI validation with UC prerequisite checks
├── .github/workflows/
│   ├── validate-packages.yml       # PR validation of access-packages YAML
│   ├── build-ui.yml                # React app lint + build check
│   ├── terraform-validate.yml      # Terraform module validation
│   ├── sync-fixtures.yml           # Auto-regenerate fixtures on YAML change
│   └── deploy-demo.yml             # Manual dispatch → GitHub Pages or Azure SWA
└── docs/
    ├── V2.0-LAUNCH-NOTES.md        # Staged rollout plan + Databricks design decisions
    ├── architecture.md             # Technical architecture deep dive
    └── runbook.md                  # Operational procedures
```

## Persona Access Packages

| Persona | Platforms | Workspace Role | Key Grants |
|---------|-----------|---------------|------------|
| Data Engineer | Fabric | Contributor | Item Read/ReadAll, SQL SELECT+INSERT on staging |
| Data Office | Fabric | Viewer | Item Read, SQL SELECT on curated views |
| Analytics Team | Fabric | Viewer | Read+Build semantic models, SQL SELECT |
| Service Account | Fabric | Contributor | Read/ReadAll/Execute, SQL db_datareader |
| Databricks Engineer | Fabric + Databricks | Contributor | UC grants (staging r/w, curated r/o), workspace ACLs, SCIM |
| Databricks ML Team | Fabric + Databricks | Contributor | UC model registry, feature tables, serving endpoints, DLT |

## End-to-End Flow

1. **User requests access** via Entra ID My Access portal, selecting a persona package
2. **Approval workflow** runs (manager + platform team approval chain)
3. **Group membership updated** — user added to Entra security group
4. **Event fires webhook** — Microsoft Graph subscription triggers Azure Function
5. **Provider registry dispatches** to platform-specific providers (Fabric, Databricks, or both)
6. **Permissions propagated** across workspace roles, item sharing, UC grants, workspace ACLs, SCIM entitlements
7. **Audit event logged** to Log Analytics; scheduled drift detector validates state

## CI/CD

| Workflow | Trigger | Action |
|----------|---------|--------|
| `validate-packages.yml` | PR to `access-packages/` | Schema + UC prerequisite validation |
| `build-ui.yml` | PR to `control-plane-ui/` | Lint + TypeScript + Vite build |
| `terraform-validate.yml` | PR to `terraform/` | `terraform validate` for all 6 modules |
| `sync-fixtures.yml` | PR to `access-packages/` | Regenerate fixtures, auto-commit |
| `deploy-demo.yml` | Manual dispatch | Build UI → deploy to GitHub Pages or Azure SWA |

## Prerequisites

- Azure subscription with Fabric capacity provisioned
- Entra ID P2 license (for Access Packages / Identity Governance)
- Terraform >= 1.7
- Python 3.11+ (Azure Functions runtime, `pyyaml` and `jsonschema` for validation)
- Node.js 20+ (control plane UI)
- Azure CLI authenticated with sufficient privileges

For demo only: **Node.js 20+** is the only requirement.

## Documentation

- [V2.0 Launch Notes](docs/V2.0-LAUNCH-NOTES.md) — Multi-platform rollout plan, Databricks permission model, branch dependency graph
- [Architecture Deep Dive](docs/architecture.md) — Technical architecture and design decisions
- [Operations Runbook](docs/runbook.md) — Day-to-day operational procedures and troubleshooting

## License

MIT
