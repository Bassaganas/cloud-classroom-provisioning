variable "owner" {
  description = "Resource owner tag"
  type        = string
}

variable "base_domain" {
  description = "Base DNS domain for Route53 lookup"
  type        = string
}

variable "shared_core_environment" {
  description = "Environment key used for shared-core naming"
  type        = string
}

variable "shared_core_ami_id" {
  description = "AMI ID for the shared-core EC2 host"
  type        = string
}

variable "shared_core_instance_type" {
  description = "EC2 instance type for the shared-core host"
  type        = string
}

variable "shared_core_subnet_id" {
  description = "Subnet ID for the shared-core EC2 host"
  type        = string
}

variable "shared_core_key_name" {
  description = "EC2 key pair name used for SSH access"
  type        = string
}

variable "shared_core_ssh_host" {
  description = "Optional override for shared-core SSH host"
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

variable "shared_core_manage_route53_records" {
  description = "Whether this module should manage Route53 records for shared-core domains"
  type        = bool
  default     = true
}

variable "shared_core_security_group_id" {
  description = "Security group ID override for shared-core host"
  type        = string
}

variable "common_subnet_id" {
  description = "Default subnet ID from common module"
  type        = string
}

variable "common_shared_core_security_group_id" {
  description = "Shared-core security group ID from common module"
  type        = string
}

variable "common_ec2_iam_instance_profile_name" {
  description = "EC2 instance profile name from common module"
  type        = string
}
