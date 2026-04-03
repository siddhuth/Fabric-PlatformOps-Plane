# terraform/main.tf
# Root module that composes workspace, entra-groups, and capacity modules.
# Each environment (dev/staging/prod) provides its own tfvars.

# ---------------------------------------------------------------------------
# Load access package definitions from YAML
# The YAML files in access-packages/definitions/ are the source of truth.
# ---------------------------------------------------------------------------
locals {
  access_package_files = fileset("${path.root}/../../access-packages/definitions", "*.yaml")

  access_packages = {
    for f in local.access_package_files :
    trimsuffix(f, ".yaml") => yamldecode(
      file("${path.root}/../../access-packages/definitions/${f}")
    )
  }

  # Flatten to workspace role assignments
  workspace_role_assignments = [
    for name, pkg in local.access_packages : {
      entra_group_name      = pkg.package.entra_group
      entra_group_object_id = module.entra_groups.group_ids[name]
      workspace_role        = pkg.grants.workspace.role
    }
  ]
}

# ---------------------------------------------------------------------------
# Entra Security Groups
# ---------------------------------------------------------------------------
module "entra_groups" {
  source = "./modules/entra-groups"

  access_packages = [
    for name, pkg in local.access_packages : {
      name             = name
      entra_group_name = pkg.package.entra_group
      description      = pkg.package.name
    }
  ]

  group_owners        = var.platform_team_object_ids
  resource_group_name = var.resource_group_name
  location            = var.location
  subscription_id     = var.subscription_id
}

# ---------------------------------------------------------------------------
# Fabric Workspaces
# One workspace module invocation per workspace defined in the environment.
# ---------------------------------------------------------------------------
module "workspaces" {
  source   = "./modules/workspace"
  for_each = var.workspaces

  capacity_name          = var.capacity_name
  workspace_display_name = each.value.display_name
  workspace_description  = each.value.description
  access_packages        = local.workspace_role_assignments

  service_principals = var.service_principals

  git_provider_config = lookup(each.value, "git_config", null)
}

# ---------------------------------------------------------------------------
# Databricks Workspace
# ---------------------------------------------------------------------------
module "databricks_workspace" {
  source = "./modules/databricks-workspace"
  count  = var.databricks_workspace != null ? 1 : 0

  workspace_name              = var.databricks_workspace.name
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = var.databricks_workspace.sku
  managed_resource_group_name = var.databricks_workspace.managed_resource_group_name
  metastore_id                = var.databricks_workspace.metastore_id
}

# ---------------------------------------------------------------------------
# Databricks Unity Catalog — Catalogs & Schemas
# ---------------------------------------------------------------------------
module "databricks_uc_catalog" {
  source   = "./modules/databricks-uc-catalog"
  for_each = var.databricks_catalogs

  catalog_name   = each.key
  catalog_comment = each.value.comment
  schemas        = each.value.schemas
  catalog_grants = each.value.catalog_grants

  depends_on = [module.databricks_workspace]
}

# ---------------------------------------------------------------------------
# Databricks SCIM — Groups, Entitlements, Membership
# ---------------------------------------------------------------------------
module "databricks_scim" {
  source = "./modules/databricks-scim"
  count  = length(var.databricks_scim_groups) > 0 ? 1 : 0

  groups = var.databricks_scim_groups

  depends_on = [module.databricks_workspace]
}
