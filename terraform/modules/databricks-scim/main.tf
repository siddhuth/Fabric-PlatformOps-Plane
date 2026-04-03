# terraform/modules/databricks-scim/main.tf
# Provisions Databricks groups via SCIM, synced from Entra ID.
# Manages entitlements and group membership for access packages.

# ---------------------------------------------------------------------------
# SCIM Group
# ---------------------------------------------------------------------------
resource "databricks_group" "this" {
  for_each = { for g in var.groups : g.display_name => g }

  display_name = each.value.display_name

  # Entitlements
  workspace_access       = contains(each.value.entitlements, "workspace-access")
  databricks_sql_access  = contains(each.value.entitlements, "databricks-sql-access")
  allow_cluster_create   = contains(each.value.entitlements, "allow-cluster-create")
  allow_instance_pool_create = contains(each.value.entitlements, "allow-instance-pool-create")
}

# ---------------------------------------------------------------------------
# Entra ID Group Connector (AAD sync)
# Maps Databricks SCIM groups to Entra ID security groups for automatic
# membership synchronization via the SCIM provisioning connector.
# ---------------------------------------------------------------------------
resource "databricks_group" "entra_connector" {
  for_each = {
    for g in var.groups : g.display_name => g
    if g.entra_group_id != ""
  }

  display_name = "${each.value.display_name}-entra-sync"
  external_id  = each.value.entra_group_id
}

# ---------------------------------------------------------------------------
# Group Membership (nested groups: entra connector → SCIM group)
# ---------------------------------------------------------------------------
resource "databricks_group_member" "entra_sync" {
  for_each = {
    for g in var.groups : g.display_name => g
    if g.entra_group_id != ""
  }

  group_id  = databricks_group.this[each.key].id
  member_id = databricks_group.entra_connector[each.key].id
}

# ---------------------------------------------------------------------------
# Service Principal (optional — for automation)
# ---------------------------------------------------------------------------
resource "databricks_service_principal" "this" {
  for_each = { for sp in var.service_principals : sp.application_id => sp }

  application_id = each.value.application_id
  display_name   = each.value.display_name

  workspace_access      = each.value.workspace_access
  databricks_sql_access = each.value.databricks_sql_access
}
