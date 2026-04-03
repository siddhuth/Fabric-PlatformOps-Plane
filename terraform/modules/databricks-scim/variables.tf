variable "groups" {
  description = "SCIM groups to provision in the Databricks workspace."
  type = list(object({
    display_name   = string
    entra_group_id = string
    entitlements   = list(string)
  }))
}

variable "service_principals" {
  description = "Service principals to register in the workspace."
  type = list(object({
    application_id        = string
    display_name          = string
    workspace_access      = optional(bool, true)
    databricks_sql_access = optional(bool, false)
  }))
  default = []
}
