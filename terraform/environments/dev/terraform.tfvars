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

# ---------------------------------------------------------------------------
# Databricks Configuration
# ---------------------------------------------------------------------------
databricks_host = "" # e.g., "https://adb-1234567890123456.7.azuredatabricks.net"

databricks_workspace = {
  name         = "dbw-sales-dev"
  sku          = "premium"
  metastore_id = "" # Populate after metastore is created
}

databricks_catalogs = {
  sales_catalog = {
    comment = "Sales domain data catalog — staging, curated, and raw layers"
    schemas = [
      {
        name    = "staging"
        comment = "Raw ingestion / staging area"
        grants = [
          {
            principal  = "sg-fabric-de-sales"
            privileges = ["USE_SCHEMA", "SELECT", "INSERT", "CREATE_TABLE", "MODIFY"]
          }
        ]
      },
      {
        name    = "curated"
        comment = "Curated / business-ready data"
        grants = [
          {
            principal  = "sg-fabric-de-sales"
            privileges = ["USE_SCHEMA", "SELECT"]
          },
          {
            principal  = "sg-fabric-ml-sales"
            privileges = ["USE_SCHEMA", "SELECT"]
          }
        ]
      },
      {
        name    = "raw"
        comment = "Raw external data sources"
        grants = [
          {
            principal  = "sg-fabric-de-sales"
            privileges = ["USE_SCHEMA", "SELECT"]
          }
        ]
      }
    ]
    catalog_grants = [
      {
        principal  = "sg-fabric-de-sales"
        privileges = ["USE_CATALOG"]
      },
      {
        principal  = "sg-fabric-ml-sales"
        privileges = ["USE_CATALOG"]
      }
    ]
  }

  ml_catalog = {
    comment = "ML platform catalog — models, features, experiments, serving"
    schemas = [
      {
        name    = "models"
        comment = "ML model registry"
        grants = [
          {
            principal  = "sg-fabric-ml-sales"
            privileges = ["USE_SCHEMA", "CREATE_MODEL", "SELECT"]
          }
        ]
      },
      {
        name    = "features"
        comment = "Feature store tables"
        grants = [
          {
            principal  = "sg-fabric-ml-sales"
            privileges = ["USE_SCHEMA", "CREATE_TABLE", "CREATE_FUNCTION", "SELECT"]
          }
        ]
      },
      {
        name    = "experiments"
        comment = "MLflow experiment tracking"
        grants = [
          {
            principal  = "sg-fabric-ml-sales"
            privileges = ["USE_SCHEMA", "CREATE_TABLE", "SELECT"]
          }
        ]
      },
      {
        name    = "serving"
        comment = "Model serving endpoints"
        grants = [
          {
            principal  = "sg-fabric-ml-sales"
            privileges = ["USE_SCHEMA", "CREATE_FUNCTION", "SELECT"]
          }
        ]
      }
    ]
    catalog_grants = [
      {
        principal  = "sg-fabric-ml-sales"
        privileges = ["USE_CATALOG"]
      }
    ]
  }
}

databricks_scim_groups = [
  {
    display_name   = "sg-fabric-de-sales"
    entra_group_id = "" # Populate with Entra group object ID
    entitlements   = ["workspace-access", "databricks-sql-access"]
  },
  {
    display_name   = "sg-fabric-ml-sales"
    entra_group_id = "" # Populate with Entra group object ID
    entitlements   = ["workspace-access", "databricks-sql-access", "allow-cluster-create"]
  },
  {
    display_name   = "sg-fabric-analytics-sales"
    entra_group_id = "" # Populate with Entra group object ID
    entitlements   = ["workspace-access", "databricks-sql-access"]
  }
]
