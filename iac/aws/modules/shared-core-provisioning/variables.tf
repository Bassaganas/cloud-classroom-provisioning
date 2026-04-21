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

variable "workshop_name" {
  description = "Workshop identifier passed to provision-student.sh as WORKSHOP_NAME env var"
  type        = string
  default     = "fellowship"
}

variable "sut_bucket_name" {
  description = "Name of the S3 SUT bucket; passed to provision-student.sh as SUT_BUCKET so it can download exercises artifacts"
  type        = string
  default     = ""
}
