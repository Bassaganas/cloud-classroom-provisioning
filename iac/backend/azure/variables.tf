variable "resource_group_name" {
  description = "Name of the resource group for backend resources"
  type        = string
}

variable "location" {
  description = "Azure region to deploy the backend resources"
  type        = string
  default     = "westeurope"
}

variable "storage_account_name" {
  description = "Name of the storage account for storing Terraform state"
  type        = string
}

variable "key_vault_name" {
  description = "Name of the key vault for storing sensitive values"
  type        = string
}
