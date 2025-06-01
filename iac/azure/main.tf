terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {
  # Azure AD provider configuration
}

# Generate random string for storage account name
resource "random_string" "storage_account_suffix" {
  length  = 8
  special = false
  upper   = false
}

# Generate timestamp for unique naming
resource "random_string" "timestamp" {
  length  = 4
  special = false
  upper   = false
}

# Create resource group for classroom
resource "azurerm_resource_group" "function_rg" {
  name     = "rg-${var.classroom_name}-${var.environment}-${random_string.timestamp.result}"
  location = "eastasia"
  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom-provisioning"
  }
}

# Create storage account for function app
resource "azurerm_storage_account" "function_storage" {
  name                     = "st${replace(var.classroom_name, "-", "")}${random_string.timestamp.result}"
  resource_group_name      = azurerm_resource_group.function_rg.name
  location                 = azurerm_resource_group.function_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  depends_on               = [azurerm_resource_group.function_rg]
}

# Create App Service Plan for Function App
resource "azurerm_service_plan" "function_plan" {
  name                = "asp-${var.environment}-${var.classroom_name}-${random_string.timestamp.result}"
  resource_group_name = azurerm_resource_group.function_rg.name
  location            = azurerm_resource_group.function_rg.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption plan
  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom-provisioning"
  }
  depends_on = [azurerm_resource_group.function_rg]
}

# Create function app
resource "azurerm_linux_function_app" "user_management" {
  name                       = "func-${var.classroom_name}-${var.environment}-${random_string.timestamp.result}"
  resource_group_name        = azurerm_resource_group.function_rg.name
  location                   = azurerm_resource_group.function_rg.location
  service_plan_id            = azurerm_service_plan.function_plan.id
  storage_account_name       = azurerm_storage_account.function_storage.name
  storage_account_access_key = azurerm_storage_account.function_storage.primary_access_key

  site_config {
    application_stack {
      python_version = "3.9"
    }
    cors {
      allowed_origins     = ["*"]
      support_credentials = false
    }
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME"       = "python"
    "WEBSITE_RUN_FROM_PACKAGE"       = "1"
    "AZURE_SUBSCRIPTION_ID"          = data.azurerm_subscription.current.subscription_id
    "AZURE_TENANT_ID"                = data.azurerm_client_config.current.tenant_id
    "AZURE_CLIENT_ID"                = azuread_application.classroom_app.client_id
    "AZURE_CLIENT_SECRET"            = azuread_application_password.classroom_secret.value
    "AZURE_DOMAIN"                   = "paulabassaganasgmail.onmicrosoft.com"
    "DESTROY_KEY"                    = var.destroy_key
    "CLASSROOM_NAME"                 = var.classroom_name
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    "STUDENTS_GROUP_ID"              = azuread_group.students.object_id
    "AZURE_KEY_VAULT_URL"            = azurerm_key_vault.classroom.vault_uri
  }

  identity {
    type = "SystemAssigned"
  }

  depends_on = [
    azurerm_resource_group.function_rg,
    azurerm_storage_account.function_storage,
    azurerm_service_plan.function_plan
  ]
}

# Create Key Vault
resource "azurerm_key_vault" "classroom" {
  name                = "kv${replace(var.classroom_name, "-", "")}${var.environment}${random_string.timestamp.result}"
  location            = azurerm_resource_group.function_rg.location
  resource_group_name = azurerm_resource_group.function_rg.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Enable RBAC for Key Vault
  enable_rbac_authorization = true

  # Enable Soft Delete and Purge Protection
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
}

# Get current client configuration
data "azurerm_client_config" "current" {}

# Add this role assignment for the function app's managed identity
resource "azurerm_role_assignment" "function_rbac_admin" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_linux_function_app.user_management.identity[0].principal_id

  depends_on = [azurerm_linux_function_app.user_management]
}

# Add role assignment for Microsoft Graph API

# Output the function URL
output "function_url" {
  value = "https://${azurerm_linux_function_app.user_management.default_hostname}/api/create_user"
}

# Add this if not already present
data "azurerm_subscription" "current" {}

# Get Microsoft Graph service principal
data "azuread_service_principal" "msgraph" {
  client_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph API ID
}

# Create Azure AD App Registration
resource "azuread_application" "classroom_app" {
  display_name = "classroom-${var.classroom_name}-${var.environment}"
  owners       = [data.azurerm_client_config.current.object_id]

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph API ID

    # User.ReadWrite.All permission
    resource_access {
      id   = "741f803b-c850-494e-b5df-cde7c675a1ca" # User.ReadWrite.All
      type = "Role"                                 # "Role" means application permission
    }

    # Group.ReadWrite.All permission
    resource_access {
      id   = "62a82d76-70ea-41e2-9197-370581804d09" # Group.ReadWrite.All
      type = "Role"                                 # "Role" means application permission
    }
  }
}

# Create service principal and its secret
resource "azuread_service_principal" "classroom_sp" {
  client_id = azuread_application.classroom_app.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

resource "azuread_application_password" "classroom_secret" {
  application_id = azuread_application.classroom_app.id
  display_name   = "classroom-secret"
  end_date       = "2099-01-01T01:02:03Z"
}

# Add outputs
output "client_id" {
  value       = azuread_application.classroom_app.client_id
  description = "The Client ID of the Azure AD application"
}

output "client_secret" {
  value       = azuread_application_password.classroom_secret.value
  description = "The Client Secret of the Azure AD application"
  sensitive   = true
}

output "tenant_id" {
  value       = data.azurerm_client_config.current.tenant_id
  description = "The Tenant ID of the Azure AD"
}

output "tenant_domain" {
  value       = var.tenant_domain
  description = "The domain of the Azure AD tenant"
}

# Create security group for students
resource "azuread_group" "students" {
  display_name     = "classroom-students"
  security_enabled = true
}

# Create security group for stuents service principal
resource "azuread_group" "students_sp" {
  display_name     = "classroom-students-sp"
  security_enabled = true
}

# Output the students group ID for the Azure Function
output "students_group_id" {
  value = azuread_group.students.object_id
}


# Assign roles to the function app
resource "azurerm_role_assignment" "function_app_management" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "FunctionAppManagement"
  principal_id         = azurerm_linux_function_app.user_management.identity[0].principal_id
}

# Assign roles to the students group
resource "azurerm_role_assignment" "student_console_access" {
  scope                = azurerm_resource_group.function_rg.id
  role_definition_name = "StudentConsoleUser"
  principal_id         = azuread_group.students.object_id
}

# Assign roles to the students group service principal
resource "azurerm_role_assignment" "terraform_deployer_group" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "TerraformDeployerRole"
  principal_id         = azuread_group.students_sp.object_id
}

# Add admin consent for the application permissions
resource "azuread_app_role_assignment" "graph_group_readwrite" {
  app_role_id         = "62a82d76-70ea-41e2-9197-370581804d09" # Group.ReadWrite.All
  principal_object_id = azuread_service_principal.classroom_sp.object_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

resource "azuread_app_role_assignment" "graph_user_readwrite" {
  app_role_id         = "741f803b-c850-494e-b5df-cde7c675a1ca" # User.ReadWrite.All
  principal_object_id = azuread_service_principal.classroom_sp.object_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

# Create service principal for Terraform deployments
resource "azuread_application" "terraform_sp" {
  display_name = "terraform-${var.classroom_name}-${var.environment}"
  owners       = [data.azurerm_client_config.current.object_id]
}

resource "azuread_service_principal" "terraform_sp" {
  client_id = azuread_application.terraform_sp.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

resource "azuread_application_password" "terraform_secret_current" {
  application_id = azuread_application.terraform_sp.id
  display_name   = "terraform-secret-current"
  end_date       = timeadd(timestamp(), "168h") # 7 days
}

resource "azuread_application_password" "terraform_secret_next" {
  application_id = azuread_application.terraform_sp.id
  display_name   = "terraform-secret-next"
  # Start valid in 6 days, end in 13 days (overlap of 1 day)
  start_date = timeadd(timestamp(), "144h") # 6 days
  end_date   = timeadd(timestamp(), "312h") # 13 days
}

# Grant permissions to the current user (running Terraform)
resource "azurerm_role_assignment" "keyvault_admin" {
  scope                = azurerm_key_vault.classroom.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Wait for RBAC propagation
resource "time_sleep" "wait_30_seconds" {
  depends_on      = [azurerm_role_assignment.keyvault_admin]
  create_duration = "30s"
}

# Make Key Vault secrets depend on the RBAC propagation
resource "azurerm_key_vault_secret" "terraform_client_id" {
  depends_on   = [time_sleep.wait_30_seconds]
  name         = "terraform-client-id"
  value        = azuread_application.terraform_sp.client_id
  key_vault_id = azurerm_key_vault.classroom.id
}

resource "azurerm_key_vault_secret" "terraform_client_secret_current" {
  depends_on      = [time_sleep.wait_30_seconds]
  name            = "terraform-client-secret-current"
  value           = azuread_application_password.terraform_secret_current.value
  key_vault_id    = azurerm_key_vault.classroom.id
  expiration_date = timeadd(timestamp(), "168h") # 7 days
}

resource "azurerm_key_vault_secret" "terraform_client_secret_next" {
  depends_on      = [time_sleep.wait_30_seconds]
  name            = "terraform-client-secret-next"
  value           = azuread_application_password.terraform_secret_next.value
  key_vault_id    = azurerm_key_vault.classroom.id
  expiration_date = timeadd(timestamp(), "312h") # 13 days
}

# Give function app access to Key Vault
resource "azurerm_role_assignment" "function_keyvault_reader" {
  scope                = azurerm_key_vault.classroom.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_function_app.user_management.identity[0].principal_id
}

# Add service principal to the students_sp group
resource "azuread_group_member" "sp_group_member" {
  group_object_id  = azuread_group.students_sp.object_id
  member_object_id = azuread_service_principal.terraform_sp.object_id
}


# Add these outputs
output "terraform_client_id" {
  value       = azuread_application.terraform_sp.client_id
  description = "The Client ID of the Terraform service principal"
}

output "terraform_client_secret" {
  value       = azuread_application_password.terraform_secret_current.value
  description = "The Client Secret of the Terraform service principal"
  sensitive   = true
}

output "key_vault_name" {
  value = azurerm_key_vault.classroom.name
}

# Add Key Vault Secrets User role for the classroom service principal
resource "azurerm_role_assignment" "classroom_sp_keyvault_reader" {
  scope                = azurerm_key_vault.classroom.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azuread_service_principal.classroom_sp.object_id

  depends_on = [
    azurerm_key_vault.classroom,
    azuread_service_principal.classroom_sp
  ]
}


