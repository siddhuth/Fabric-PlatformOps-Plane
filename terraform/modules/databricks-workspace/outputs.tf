output "workspace_id" {
  description = "Databricks workspace ID (numeric)."
  value       = azurerm_databricks_workspace.this.workspace_id
}

output "workspace_url" {
  description = "Databricks workspace URL."
  value       = "https://${azurerm_databricks_workspace.this.workspace_url}"
}

output "resource_id" {
  description = "Azure resource ID of the Databricks workspace."
  value       = azurerm_databricks_workspace.this.id
}

output "managed_resource_group_id" {
  description = "ID of the managed resource group."
  value       = azurerm_databricks_workspace.this.managed_resource_group_id
}
