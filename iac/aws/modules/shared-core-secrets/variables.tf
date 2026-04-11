variable "owner" {
  description = "Resource owner tag"
  type        = string
}

variable "shared_core_environment" {
  description = "Environment key used for shared-core SSM and Secrets Manager paths"
  type        = string
}

variable "shared_core_ssh_private_key" {
  description = "SSH private key used by the shared-core deploy workflow"
  type        = string
  sensitive   = true
}

variable "shared_core_gh_repo_token" {
  description = "GitHub token used by the shared-core deploy workflow to clone the repository"
  type        = string
  sensitive   = true
}

variable "shared_core_jenkins_admin_password" {
  description = "Jenkins admin password for the shared core stack"
  type        = string
  sensitive   = true
}

variable "shared_core_gitea_admin_password" {
  description = "Gitea admin password for the shared core stack"
  type        = string
  sensitive   = true
}
