# modules/workspace/main.tf
# Provisions a Fabric workspace with role assignments derived from access package definitions.

data "fabric_capacity" "this" {
  display_name = var.capacity_name
}

# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------
resource "fabric_workspace" "this" {
  display_name = var.workspace_display_name
  description  = var.workspace_description
  capacity_id  = data.fabric_capacity.this.id
}

# ---------------------------------------------------------------------------
# Git Integration (optional)
# ---------------------------------------------------------------------------
resource "fabric_workspace_git" "this" {
  count        = var.git_provider_config != null ? 1 : 0
  workspace_id = fabric_workspace.this.id

  initialization_strategy = "PreferWorkspace"

  git_provider_details = {
    git_provider_type = var.git_provider_config.provider_type
    owner_name        = var.git_provider_config.owner
    repository_name   = var.git_provider_config.repository
    branch_name       = var.git_provider_config.branch
    directory_name    = var.git_provider_config.directory
  }
}

# ---------------------------------------------------------------------------
# Workspace Role Assignments
# Role assignments are driven by the access_packages variable which maps
# Entra security group object IDs to Fabric workspace roles.
#
# Supported roles: Admin, Member, Contributor, Viewer
# ---------------------------------------------------------------------------
resource "fabric_workspace_role_assignment" "groups" {
  for_each = {
    for pkg in var.access_packages : pkg.entra_group_name => pkg
  }

  workspace_id = fabric_workspace.this.id

  principal = {
    id   = each.value.entra_group_object_id
    type = "Group"
  }

  role = each.value.workspace_role
}

# ---------------------------------------------------------------------------
# Service Principal Role Assignments
# Dedicated block for SPN identities that need workspace access for
# automated jobs (refresh, pipeline execution, API calls).
# ---------------------------------------------------------------------------
resource "fabric_workspace_role_assignment" "service_principals" {
  for_each = {
    for spn in var.service_principals : spn.display_name => spn
  }

  workspace_id = fabric_workspace.this.id

  principal = {
    id   = each.value.object_id
    type = "ServicePrincipal"
  }

  role = each.value.workspace_role
}
