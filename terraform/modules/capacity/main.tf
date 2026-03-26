# modules/capacity/main.tf
# Provisions a Fabric capacity in Azure and configures admin settings.
# Skip this module if capacity is pre-provisioned or managed externally.

resource "azurerm_resource_group" "fabric" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_fabric_capacity" "this" {
  name                = var.capacity_name
  resource_group_name = azurerm_resource_group.fabric.name
  location            = var.location

  sku {
    name = var.sku_name # F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024
    tier = "Fabric"
  }

  administration {
    members = var.capacity_admins
  }

  tags = var.tags
}

output "capacity_id" {
  value = azurerm_fabric_capacity.this.id
}

output "capacity_name" {
  value = azurerm_fabric_capacity.this.name
}
