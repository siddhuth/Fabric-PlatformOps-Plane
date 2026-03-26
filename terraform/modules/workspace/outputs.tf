# modules/workspace/outputs.tf

output "workspace_id" {
  description = "The ID of the provisioned Fabric workspace."
  value       = fabric_workspace.this.id
}

output "workspace_display_name" {
  description = "The display name of the provisioned workspace."
  value       = fabric_workspace.this.display_name
}

output "role_assignments" {
  description = "Map of Entra group names to their assigned workspace roles."
  value = {
    for k, v in fabric_workspace_role_assignment.groups :
    k => v.role
  }
}
