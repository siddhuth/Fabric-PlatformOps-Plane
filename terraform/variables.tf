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
