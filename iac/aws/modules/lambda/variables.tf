variable "environment" {
  description = "The environment name"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of the IAM role for Lambda execution"
  type        = string
}

variable "status_lambda_url" {
  description = "URL of the status Lambda function (for user_management dependency)"
  type        = string
  default     = ""
}

variable "subnet_id" {
  description = "Subnet ID for EC2 instances (for instance_manager)"
  type        = string
}

variable "security_group_ids" {
  description = "Security group IDs for EC2 instances (for instance_manager)"
  type        = list(string)
}

variable "iam_instance_profile_name" {
  description = "IAM instance profile name for EC2 instances (for instance_manager)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type (for instance_manager)"
  type        = string
}

variable "admin_cleanup_interval_days" {
  description = "Number of days after which admin instances should be automatically deleted"
  type        = number
  default     = 7
}

variable "admin_cleanup_schedule" {
  description = "Schedule expression for admin instance cleanup"
  type        = string
  default     = "cron(0 2 ? * SUN *)"
}

variable "functions_path" {
  description = "Path to the functions packages directory"
  type        = string
  default     = "../../functions/packages"
}

variable "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret for instance manager password"
  type        = string
  default     = ""
}

