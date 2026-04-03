variable "workspace_name" {
  description = "Name of the Azure Databricks workspace."
  type        = string
}

variable "resource_group_name" {
  description = "Azure resource group for the workspace."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "eastus"
}

variable "sku" {
  description = "Databricks workspace pricing tier."
  type        = string
  default     = "premium"

  validation {
    condition     = contains(["standard", "premium", "trial"], var.sku)
    error_message = "SKU must be standard, premium, or trial."
  }
}

variable "managed_resource_group_name" {
  description = "Resource group for Databricks-managed resources. Auto-generated if omitted."
  type        = string
  default     = ""
}

variable "metastore_id" {
  description = "Unity Catalog metastore ID to assign to this workspace. Leave empty to skip."
  type        = string
  default     = ""
}

variable "vnet_config" {
  description = "Optional VNet injection config for the workspace."
  type = object({
    virtual_network_id = string
    public_subnet_name = string
    private_subnet_name = string
    public_subnet_nsg_association_id  = string
    private_subnet_nsg_association_id = string
  })
  default = null
}

variable "tags" {
  description = "Resource tags."
  type        = map(string)
  default     = {}
}
