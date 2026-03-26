# environments/dev/terraform.tfvars
# Development environment configuration

capacity_name    = "fabric-dev-capacity"
resource_group_name = "rg-fabric-access-platform-dev"
location         = "eastus"
subscription_id  = "00000000-0000-0000-0000-000000000000" # Replace

platform_team_object_ids = [
  # "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", # Platform Team Lead
  # "ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj", # Platform Engineer
]

workspaces = {
  sales-lakehouse = {
    display_name = "Sales Lakehouse - Dev"
    description  = "Development workspace for the sales domain lakehouse and mirrored databases."
    git_config = {
      provider_type = "GitHub"
      owner         = "your-org"
      repository    = "fabric-sales-lakehouse"
      branch        = "dev"
      directory     = "/fabric"
    }
  }

  marketing-analytics = {
    display_name = "Marketing Analytics - Dev"
    description  = "Development workspace for marketing domain analytics and semantic models."
    git_config   = null
  }
}

service_principals = [
  # {
  #   display_name   = "spn-fabric-automation-dev"
  #   object_id      = "11111111-2222-3333-4444-555555555555"
  #   workspace_role = "Contributor"
  # }
]
