terraform {
  required_version = ">= 1.0.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group for backend resources
resource "azurerm_resource_group" "terraform_state" {
  name     = var.resource_group_name
  location = var.location
  tags = {
    Environment = "production"
    Owner       = "terraform"
    Project     = "classroom-provisioning"
    Company     = "TestingFantasy"
  }
}

# Storage Account for storing Terraform state
resource "azurerm_storage_account" "terraform_state" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.terraform_state.name
  location                 = azurerm_resource_group.terraform_state.location
  account_tier             = "Standard"
  account_replication_type = "GRS"
  min_tls_version          = "TLS1_2"

  tags = {
    Environment = "production"
    Owner       = "terraform"
    Project     = "classroom-provisioning"
    Company     = "TestingFantasy"
  }

  blob_properties {
    versioning_enabled = true
  }
}

# Container for Terraform state files
resource "azurerm_storage_container" "terraform_state" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.terraform_state.name
  container_access_type = "private"
}

# Key Vault for storing sensitive values
resource "azurerm_key_vault" "terraform_state" {
  name                = var.key_vault_name
  location            = azurerm_resource_group.terraform_state.location
  resource_group_name = azurerm_resource_group.terraform_state.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  purge_protection_enabled = true

  tags = {
    Environment = "production"
    Owner       = "terraform"
    Project     = "classroom-provisioning"
    Company     = "TestingFantasy"
  }
}

# Access policy for the current user/service principal
resource "azurerm_key_vault_access_policy" "terraform_state" {
  key_vault_id = azurerm_key_vault.terraform_state.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get",
    "List",
    "Set"
  ]
}

# Get current Azure configuration
data "azurerm_client_config" "current" {}

# Outputs for use in other configurations
output "resource_group_name" {
  value = azurerm_resource_group.terraform_state.name
}

output "storage_account_name" {
  value = azurerm_storage_account.terraform_state.name
}

output "container_name" {
  value = azurerm_storage_container.terraform_state.name
}

output "key_vault_name" {
  value = azurerm_key_vault.terraform_state.name
}
