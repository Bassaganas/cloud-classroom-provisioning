variable "environment" {
  description = "The environment name (dev, staging, prod)"
  type        = string
}

variable "owner" {
  description = "Owner tag value for all resources"
  type        = string
}

variable "region" {
  description = "AWS region where resources are deployed"
  type        = string
}

variable "instance_manager_lambda_role_arn" {
  description = "IAM role ARN of the instance-manager Lambda — granted sqs:SendMessage on the provisioning queue"
  type        = string
}
