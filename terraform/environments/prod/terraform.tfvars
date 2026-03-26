# environments/prod/terraform.tfvars
# Production environment configuration

capacity_name       = "fabric-prod-capacity"
resource_group_name = "rg-fabric-access-platform-prod"
location            = "eastus"
subscription_id     = "00000000-0000-0000-0000-000000000000" # Replace

platform_team_object_ids = [
  # "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
]

workspaces = {
  sales-lakehouse = {
    display_name = "Sales Lakehouse - Prod"
    description  = "Production workspace for the sales domain lakehouse and mirrored databases."
    git_config = {
      provider_type = "GitHub"
      owner         = "your-org"
      repository    = "fabric-sales-lakehouse"
      branch        = "main"
      directory     = "/fabric"
    }
  }

  marketing-analytics = {
    display_name = "Marketing Analytics - Prod"
    description  = "Production workspace for marketing domain analytics."
    git_config   = null
  }
}

service_principals = []
