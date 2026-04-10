# Control Plane UI

React dashboard for the Fabric Access Platform — the stakeholder-facing control plane for multi-platform access governance.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | **Platform Overview** | Three platform cards (Fabric, Databricks, Snowflake) with stats, capabilities, and status |
| `/access-matrix` | **Access Matrix** | Principal x resource grid with click-to-inspect grant detail. Filterable by platform and search |
| `/provisioning` | **Provisioning Flow** | Select a trace and watch step-by-step animated execution with platform badges and timing |
| `/audit-log` | **Audit Log** | Scrollable timeline with platform-colored borders and filters by platform, action type, and search |
| `/drift` | **Drift Dashboard** | Summary stats bar + finding cards with expected-vs-actual diff display |

## Tech Stack

- React 18 + TypeScript
- Vite
- Tailwind CSS v4
- React Router v6
- Fixture-driven (reads from `demo/fixtures/` JSON files — no live API needed)

## Getting Started

```bash
cd control-plane-ui
npm install
npm run dev
```

The dev server serves at `http://localhost:5173` and loads fixture data from the `demo/fixtures/` directory.

## Build

```bash
npm run build
```

Output lands in `dist/` for static hosting (Azure Static Web Apps, GitHub Pages, etc.).
