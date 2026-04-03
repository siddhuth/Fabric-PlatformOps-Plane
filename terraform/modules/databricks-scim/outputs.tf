output "group_ids" {
  description = "Map of group display name to Databricks group ID."
  value       = { for k, g in databricks_group.this : k => g.id }
}

output "group_names" {
  description = "List of provisioned group display names."
  value       = [for g in databricks_group.this : g.display_name]
}

output "service_principal_ids" {
  description = "Map of application ID to Databricks service principal ID."
  value       = { for k, sp in databricks_service_principal.this : k => sp.id }
}
