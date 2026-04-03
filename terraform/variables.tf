# terraform/variables.tf

variable "capacity_name" {
  description = "Display name of the Fabric capacity."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for supporting infrastructure (Functions, Event Grid, etc.)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "platform_team_object_ids" {
  description = "Entra object IDs of platform team members (set as group owners)."
  type        = list(string)
}

variable "workspaces" {
  description = "Map of workspace configurations to provision."
  type = map(object({
    display_name = string
    description  = string
    git_config = optional(object({
      provider_type = string
      owner         = string
      repository    = string
      branch        = string
      directory     = string
    }))
  }))
}

variable "service_principals" {
  description = "Service principals for automated workspace access."
  type = list(object({
    display_name   = string
    object_id      = string
    workspace_role = string
  }))
  default = []
}

# ---------------------------------------------------------------------------
# Databricks Variables
# ---------------------------------------------------------------------------
variable "databricks_host" {
  description = "Databricks workspace URL (e.g., https://adb-xxx.y.azuredatabricks.net)."
  type        = string
  default     = ""
}

variable "databricks_workspace" {
  description = "Databricks workspace configuration."
  type = object({
    name                        = string
    sku                         = optional(string, "premium")
    managed_resource_group_name = optional(string, "")
    metastore_id                = optional(string, "")
  })
  default = null
}

variable "databricks_catalogs" {
  description = "Unity Catalog catalogs to provision."
  type = map(object({
    comment = optional(string, "")
    schemas = list(object({
      name    = string
      comment = string
      grants = optional(list(object({
        principal  = string
        privileges = list(string)
      })), [])
    }))
    catalog_grants = optional(list(object({
      principal  = string
      privileges = list(string)
    })), [])
  }))
  default = {}
}

variable "databricks_scim_groups" {
  description = "SCIM groups to provision in the Databricks workspace."
  type = list(object({
    display_name   = string
    entra_group_id = string
    entitlements   = list(string)
  }))
  default = []
}
