terraform {
  required_version = ">= 1.8, < 2.0"

  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "~> 1.8"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.60"
    }
  }

  backend "azurerm" {
    # Configured per environment via -backend-config
  }
}

provider "fabric" {
  # Authentication via environment variables or managed identity
  # FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET, FABRIC_TENANT_ID
}

provider "azurerm" {
  features {}
}

provider "azuread" {}

provider "databricks" {
  # Authentication via environment variables:
  # DATABRICKS_HOST, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET
  # Or configure for Azure: DATABRICKS_AZURE_CLIENT_ID, etc.
  host = var.databricks_host
}
