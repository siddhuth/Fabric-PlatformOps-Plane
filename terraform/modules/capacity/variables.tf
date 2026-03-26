# modules/capacity/variables.tf

variable "capacity_name" {
  description = "Name for the Fabric capacity resource."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to deploy capacity into."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "sku_name" {
  description = "Fabric capacity SKU (F2, F4, F8, ... F1024)."
  type        = string
  default     = "F2"
}

variable "capacity_admins" {
  description = "List of Entra user principal names to assign as capacity admins."
  type        = list(string)
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
