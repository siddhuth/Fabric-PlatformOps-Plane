# terraform/modules/databricks-uc-catalog/main.tf
# Provisions Unity Catalog catalogs and schemas, with optional managed
# storage locations and grants derived from access package definitions.

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
resource "databricks_catalog" "this" {
  name    = var.catalog_name
  comment = var.catalog_comment

  properties = merge(var.catalog_properties, {
    managed_by = "fabric-platformops-plane"
  })
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
resource "databricks_schema" "this" {
  for_each = { for s in var.schemas : s.name => s }

  catalog_name = databricks_catalog.this.name
  name         = each.value.name
  comment      = each.value.comment

  properties = {
    managed_by = "fabric-platformops-plane"
  }
}

# ---------------------------------------------------------------------------
# Storage Credential (optional — for external locations)
# ---------------------------------------------------------------------------
resource "databricks_storage_credential" "this" {
  count = var.storage_credential != null ? 1 : 0

  name = var.storage_credential.name

  azure_managed_identity {
    access_connector_id = var.storage_credential.access_connector_id
  }

  comment = "Managed by Fabric PlatformOps Plane"
}

# ---------------------------------------------------------------------------
# External Location (optional — for ADLS Gen2 backing)
# ---------------------------------------------------------------------------
resource "databricks_external_location" "this" {
  count = var.external_location != null ? 1 : 0

  name            = var.external_location.name
  url             = var.external_location.url
  credential_name = databricks_storage_credential.this[0].name
  comment         = "Managed by Fabric PlatformOps Plane"
}

# ---------------------------------------------------------------------------
# Catalog-Level Grants
# ---------------------------------------------------------------------------
resource "databricks_grants" "catalog" {
  catalog = databricks_catalog.this.name

  dynamic "grant" {
    for_each = var.catalog_grants
    content {
      principal  = grant.value.principal
      privileges = grant.value.privileges
    }
  }
}

# ---------------------------------------------------------------------------
# Schema-Level Grants
# ---------------------------------------------------------------------------
resource "databricks_grants" "schema" {
  for_each = { for s in var.schemas : s.name => s if length(s.grants) > 0 }

  schema = "${databricks_catalog.this.name}.${each.key}"

  dynamic "grant" {
    for_each = each.value.grants
    content {
      principal  = grant.value.principal
      privileges = grant.value.privileges
    }
  }

  depends_on = [databricks_schema.this]
}
