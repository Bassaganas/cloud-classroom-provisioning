variable "environment" {
  description = "Main environment label for tags"
  type        = string
}

variable "owner" {
  description = "Resource owner tag"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "github_actions_oidc_thumbprint" {
  description = "Thumbprint for GitHub Actions OIDC provider"
  type        = string
}

variable "shared_core_environment" {
  description = "Environment key used for shared-core SSM and Secrets Manager paths"
  type        = string
}

variable "shared_core_github_owner" {
  description = "GitHub organisation or user that owns the repository running the shared-core deploy workflow"
  type        = string
}

variable "shared_core_github_repo" {
  description = "GitHub repository name running the shared-core deploy workflow"
  type        = string
}

variable "shared_core_github_environment" {
  description = "GitHub Actions environment name allowed to assume the shared-core OIDC role"
  type        = string
}

variable "shared_core_deploy_secret_arn" {
  description = "ARN of the shared-core deploy secret"
  type        = string
}
