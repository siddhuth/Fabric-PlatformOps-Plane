variable "catalog_name" {
  description = "Name of the Unity Catalog catalog."
  type        = string
}

variable "catalog_comment" {
  description = "Comment / description for the catalog."
  type        = string
  default     = ""
}

variable "catalog_properties" {
  description = "Additional catalog properties."
  type        = map(string)
  default     = {}
}

variable "schemas" {
  description = "List of schemas to create within the catalog."
  type = list(object({
    name    = string
    comment = string
    grants = optional(list(object({
      principal  = string
      privileges = list(string)
    })), [])
  }))
}

variable "catalog_grants" {
  description = "Catalog-level grants (USE_CATALOG, etc.)."
  type = list(object({
    principal  = string
    privileges = list(string)
  }))
  default = []
}

variable "storage_credential" {
  description = "Optional storage credential for external locations."
  type = object({
    name                = string
    access_connector_id = string
  })
  default = null
}

variable "external_location" {
  description = "Optional external location backed by ADLS Gen2."
  type = object({
    name = string
    url  = string
  })
  default = null
}
