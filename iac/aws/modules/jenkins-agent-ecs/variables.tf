variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
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

variable "vpc_id" {
  description = "VPC ID where the agent security group is created"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID where Fargate tasks are launched (must have internet access)"
  type        = string
}

variable "shared_core_security_group_id" {
  description = "Security group ID of the shared-core Jenkins controller host"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL for the Jenkins agent image (managed at root level)"
  type        = string
}

variable "shared_core_ec2_role_name" {
  description = "Name (not ARN) of the shared-core EC2 IAM role to attach ECS permissions to"
  type        = string
}
