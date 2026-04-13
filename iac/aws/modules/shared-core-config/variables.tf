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
  description = "Route53 hosted zone ID for shared-core domains (optional - omit when manage_route53_records is false)"
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

variable "jenkins_agent_ecs_cluster_arn" {
  description = "ARN of the ECS cluster for Jenkins Fargate build agents"
  type        = string
}

variable "jenkins_agent_ecr_image" {
  description = "ECR repository URL for the Jenkins agent image (tag appended automatically)"
  type        = string
}

variable "jenkins_agent_ecs_security_group_id" {
  description = "Security group ID for Jenkins ECS Fargate agent tasks"
  type        = string
}

variable "jenkins_agent_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  type        = string
}

variable "jenkins_agent_task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "jenkins_agent_subnet_id" {
  description = "Subnet ID where Jenkins ECS Fargate agent tasks are launched"
  type        = string
}

variable "shared_core_private_ip" {
  description = "Private IP address of the shared-core EC2 instance (used for JNLP tunnel)"
  type        = string
}
