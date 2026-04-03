output "catalog_name" {
  description = "Name of the created Unity Catalog catalog."
  value       = databricks_catalog.this.name
}

output "catalog_id" {
  description = "ID of the created catalog."
  value       = databricks_catalog.this.id
}

output "schema_names" {
  description = "List of schema names created in the catalog."
  value       = [for s in databricks_schema.this : s.name]
}

output "schema_ids" {
  description = "Map of schema name to schema ID."
  value       = { for k, s in databricks_schema.this : k => s.id }
}
