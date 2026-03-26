# modules/entra-groups/main.tf
# Creates Entra ID security groups for each access package persona and
# configures Microsoft Graph event subscriptions for group membership changes.

# ---------------------------------------------------------------------------
# Security Groups — one per access package
# ---------------------------------------------------------------------------
resource "azuread_group" "access_package" {
  for_each = { for pkg in var.access_packages : pkg.name => pkg }

  display_name     = each.value.entra_group_name
  description      = "Fabric access package: ${each.value.name} — ${each.value.description}"
  security_enabled = true
  mail_enabled     = false

  owners = var.group_owners

  lifecycle {
    # Prevent Terraform from removing members managed by Entra Access Packages
    ignore_changes = [members]
  }
}

# ---------------------------------------------------------------------------
# Graph Subscription — fires webhook on group membership changes
# This subscription triggers the provisioning Azure Function when a user
# is added to or removed from any access package security group.
# ---------------------------------------------------------------------------
resource "azurerm_resource_group" "events" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_eventgrid_system_topic" "entra_events" {
  name                   = "fabric-access-entra-events"
  resource_group_name    = azurerm_resource_group.events.name
  location               = "global"
  source_arm_resource_id = "/subscriptions/${var.subscription_id}"
  topic_type             = "Microsoft.AAD.DomainName"

  # Note: For production, use Microsoft Graph Change Notifications
  # via the Graph API subscription endpoint rather than Event Grid.
  # This resource is a placeholder for the event subscription pattern.
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "group_ids" {
  description = "Map of access package names to their Entra group object IDs."
  value = {
    for k, v in azuread_group.access_package :
    k => v.object_id
  }
}

output "group_names" {
  description = "Map of access package names to their Entra group display names."
  value = {
    for k, v in azuread_group.access_package :
    k => v.display_name
  }
}
