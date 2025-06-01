terraform {
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

# Resource group for Terraform state
resource "azurerm_resource_group" "terraform_state" {
  name     = "terraform-state-rg"
  location = "eastus"
  tags = {
    Environment = "management"
    Owner       = "terraform"
    Project     = "classroom-provisioning"
  }
}

# Storage account for Terraform state
resource "azurerm_storage_account" "terraform_state" {
  name                     = "tfstateclassroom"
  resource_group_name      = azurerm_resource_group.terraform_state.name
  location                 = azurerm_resource_group.terraform_state.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

# Container for Terraform state
resource "azurerm_storage_container" "terraform_state" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.terraform_state.name
  container_access_type = "private"
}

# Output the storage account name and key for use in main.tf
output "storage_account_name" {
  value = azurerm_storage_account.terraform_state.name
}

output "storage_account_key" {
  value     = azurerm_storage_account.terraform_state.primary_access_key
  sensitive = true
}
