# terraform/modules/databricks-workspace/main.tf
# Provisions an Azure Databricks workspace with optional Unity Catalog
# metastore assignment and VNet injection.

locals {
  managed_rg = var.managed_resource_group_name != "" ? var.managed_resource_group_name : "databricks-rg-${var.workspace_name}"
}

# ---------------------------------------------------------------------------
# Azure Databricks Workspace
# ---------------------------------------------------------------------------
resource "azurerm_databricks_workspace" "this" {
  name                        = var.workspace_name
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = var.sku
  managed_resource_group_name = local.managed_rg

  dynamic "custom_parameters" {
    for_each = var.vnet_config != null ? [var.vnet_config] : []
    content {
      virtual_network_id                                   = custom_parameters.value.virtual_network_id
      public_subnet_name                                   = custom_parameters.value.public_subnet_name
      private_subnet_name                                  = custom_parameters.value.private_subnet_name
      public_subnet_network_security_group_association_id  = custom_parameters.value.public_subnet_nsg_association_id
      private_subnet_network_security_group_association_id = custom_parameters.value.private_subnet_nsg_association_id
    }
  }

  tags = merge(var.tags, {
    managed_by = "fabric-platformops-plane"
    platform   = "databricks"
  })
}

# ---------------------------------------------------------------------------
# Unity Catalog Metastore Assignment
# ---------------------------------------------------------------------------
resource "databricks_metastore_assignment" "this" {
  count = var.metastore_id != "" ? 1 : 0

  workspace_id = azurerm_databricks_workspace.this.workspace_id
  metastore_id = var.metastore_id
}
