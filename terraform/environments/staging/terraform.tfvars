# environments/staging/terraform.tfvars
# Staging environment — mirrors prod structure with reduced capacity

capacity_name       = "fabric-staging-capacity"
resource_group_name = "rg-fabric-access-platform-staging"
location            = "eastus"
subscription_id     = "00000000-0000-0000-0000-000000000000" # Replace

platform_team_object_ids = []

workspaces = {
  sales-lakehouse = {
    display_name = "Sales Lakehouse - Staging"
    description  = "Staging workspace for sales domain validation."
    git_config = {
      provider_type = "GitHub"
      owner         = "your-org"
      repository    = "fabric-sales-lakehouse"
      branch        = "staging"
      directory     = "/fabric"
    }
  }
}

service_principals = []
