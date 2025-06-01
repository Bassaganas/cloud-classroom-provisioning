variable "location" {
  description = "Azure region where resources will be created"
  type        = string
  default     = "centralus"
}

variable "environment" {
  description = "Environment name (e.g., dev, test, prod)"
  type        = string
  default     = "test"
}

variable "owner" {
  description = "Owner tag for resources"
  type        = string
  default     = "paula"
}

variable "function_app_name" {
  description = "Name of the Azure Function App"
  type        = string
  default     = "classroom-provisioning"
}

variable "subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure Tenant ID"
  type        = string
}

variable "tenant_domain" {
  description = "Azure AD tenant domain"
  type        = string
  default     = "paulabassaganasgmail.onmicrosoft.com"
}

variable "destroy_key" {
  description = "Key required to destroy all users"
  type        = string
  default     = "your-secure-destroy-key-here"
}

variable "classroom_name" {
  description = "Name of the classroom"
  type        = string
  default     = "default-classroom"
}
