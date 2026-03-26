# Control Plane UI

Platform team dashboard for managing Fabric access at scale.

## Overview

This React application provides the operational interface for the platform team to view, audit, manage, and override access assignments. It connects to:

- **Azure Functions** — For triggering provisioning/revocation and drift scans
- **Log Analytics** — For audit trail and drift reports
- **Microsoft Graph** — For Entra group membership and access package status

## Views

### Access Matrix (`/access-matrix`)
Cross-reference view showing which personas have access to which workspaces and items. Filterable by domain, team, sensitivity label, or individual user. Reads from the YAML access package definitions and validates against actual Fabric state.

### Audit Log (`/audit-log`)
Chronological history of all provisioning events, revocations, drift detections, and emergency overrides. Powered by Log Analytics queries. Supports search, date range filtering, and export to CSV.

### Override Panel (`/override`)
Emergency access grant interface for time-critical situations that cannot wait for the standard Entra approval flow. Features:
- Justification text field (required)
- Time-box selector (1h, 4h, 8h, 24h)
- Auto-revocation timer
- Post-incident review prompt

## Tech Stack

- React 18 + TypeScript
- Tailwind CSS for styling
- Azure AD authentication (MSAL React)
- Log Analytics REST API for audit data
- Azure Functions HTTP triggers for operations

## Getting Started

```bash
cd control-plane-ui
npm install
npm run dev
```

Configure `.env.local`:

```env
VITE_AZURE_CLIENT_ID=<app-registration-client-id>
VITE_AZURE_TENANT_ID=<tenant-id>
VITE_FUNCTION_APP_URL=https://func-fabric-access-xxxx.azurewebsites.net
VITE_LOG_ANALYTICS_WORKSPACE_ID=<workspace-id>
```

## Deployment

The UI can be deployed as:
- **Azure Static Web App** — Recommended for production
- **Embedded Power BI Dashboard** — Alternative for teams already in Power BI
- **Local development** — `npm run dev` for platform team testing
