# modules/workspace/variables.tf

variable "capacity_name" {
  description = "Display name of the Fabric capacity to bind the workspace to."
  type        = string
}

variable "workspace_display_name" {
  description = "Display name for the Fabric workspace."
  type        = string
}

variable "workspace_description" {
  description = "Description for the Fabric workspace."
  type        = string
  default     = ""
}

variable "access_packages" {
  description = <<-EOT
    List of access packages that define Entra group → workspace role mappings.
    Each entry corresponds to a persona access package defined in access-packages/definitions/.
  EOT
  type = list(object({
    entra_group_name      = string
    entra_group_object_id = string
    workspace_role        = string # Admin | Member | Contributor | Viewer
  }))
  default = []
}

variable "service_principals" {
  description = "Service principals requiring workspace-level access for automation."
  type = list(object({
    display_name   = string
    object_id      = string
    workspace_role = string # Typically Contributor for refresh/execute
  }))
  default = []
}

variable "git_provider_config" {
  description = "Optional Git integration configuration for the workspace."
  type = object({
    provider_type = string # AzureDevOps | GitHub
    owner         = string
    repository    = string
    branch        = string
    directory     = string
  })
  default = null
}
