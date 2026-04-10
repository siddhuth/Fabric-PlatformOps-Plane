// Platform Summary
export interface PlatformStats {
  access_packages: number
  active_users: number
  workspaces_managed?: number
  items_shared?: number
  sql_grants_active?: number
  catalogs_managed?: number
  uc_grants_active?: number
  workspace_acls_active?: number
  scim_groups_synced?: number
  last_provision?: string
  last_drift_scan?: string
  drift_findings?: number
}

export interface Platform {
  name: string
  id: string
  status: 'active' | 'coming_soon'
  version: string
  icon: string
  stats: PlatformStats
  capabilities: string[]
  eta?: string
}

export interface PlatformSummary {
  generated_at: string
  platforms: Platform[]
  totals: {
    platforms_active: number
    platforms_planned: number
    total_access_packages: number
    total_active_users: number
    total_entra_groups: number
  }
}

// Access Matrix
export interface MatrixEntry {
  principal: string
  principal_type: string
  platform: string
  resource_type: string
  resource: string
  permission: string
  package: string
  group: string
}

export interface AccessMatrix {
  generated_at: string
  total_entries: number
  platforms: string[]
  unique_principals: number
  matrix: MatrixEntry[]
}

// Provisioning
export interface ProvisionStep {
  seq: number
  ts: string
  platform: string
  layer: string
  action: string
  target: string
  detail: string
  status: 'success' | 'failed' | 'pending'
  duration_ms: number
}

export interface ProvisionTrace {
  trace_id: string
  timestamp: string
  user: { id: string; email: string; name: string; title: string }
  package: string
  group: string
  trigger: string
  platforms: string[]
  duration_ms: number
  status: 'success' | 'partial' | 'failed'
  steps: ProvisionStep[]
}

export interface ProvisioningEvents {
  generated_at: string
  total_traces: number
  traces: ProvisionTrace[]
}

// Audit Log
export interface AuditEvent {
  event_id: string
  timestamp: string
  action: string
  platform: string
  user: string
  user_name: string
  group: string
  package: string
  details: string
  status: string
  initiated_by: string
}

export interface AuditLog {
  generated_at: string
  period_days: number
  total_events: number
  events: AuditEvent[]
}

// Drift
export interface DriftFinding {
  id: string
  platform: string
  category: string
  severity: 'high' | 'medium' | 'low'
  securable: string
  principal: string
  declared: string
  actual: string
  package: string
  detail: string
  detected_at: string
}

export interface DriftResults {
  generated_at: string
  scan_timestamp: string
  total_findings: number
  summary: {
    high: number
    medium: number
    low: number
    by_platform: Record<string, number>
    by_category: Record<string, number>
  }
  findings: DriftFinding[]
}
