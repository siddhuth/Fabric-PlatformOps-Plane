# modules/entra-groups/variables.tf

variable "access_packages" {
  description = "List of access package definitions to create security groups for."
  type = list(object({
    name             = string
    entra_group_name = string
    description      = string
  }))
}

variable "group_owners" {
  description = "List of Entra user object IDs to set as group owners."
  type        = list(string)
  default     = []
}

variable "resource_group_name" {
  description = "Resource group for event infrastructure."
  type        = string
}

variable "location" {
  description = "Azure region for event infrastructure."
  type        = string
  default     = "eastus"
}

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}
