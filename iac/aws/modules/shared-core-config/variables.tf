variable "owner" {
  description = "Resource owner tag"
  type        = string
}

variable "shared_core_environment" {
  description = "Environment key used for shared-core SSM paths"
  type        = string
}

variable "shared_core_instance_id" {
  description = "EC2 instance ID for shared-core"
  type        = string
}

variable "shared_core_ssh_host" {
  description = "SSH host used by shared-core deployment workflow"
  type        = string
}

variable "shared_core_jenkins_domain" {
  description = "Public Jenkins domain for shared core"
  type        = string
}

variable "shared_core_gitea_domain" {
  description = "Public Gitea domain for shared core"
  type        = string
}

variable "shared_core_security_group_id" {
  description = "Security group ID used by shared-core host"
  type        = string
}

variable "shared_core_hosted_zone_id" {
  description = "Route53 hosted zone ID for shared-core domains"
  type        = string
  default     = null
}

variable "shared_core_gitea_admin_user" {
  description = "Gitea admin username for shared core"
  type        = string
}

variable "shared_core_gitea_admin_email" {
  description = "Gitea admin email for shared core"
  type        = string
}

variable "shared_core_gitea_org_name" {
  description = "Gitea organisation name for shared core"
  type        = string
}
