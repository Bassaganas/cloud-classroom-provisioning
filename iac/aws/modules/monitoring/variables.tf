variable "environment" {
  description = "The environment name"
  type        = string
}

variable "stop_old_instances_lambda_arn" {
  description = "ARN of the stop old instances Lambda function"
  type        = string
}

variable "admin_cleanup_lambda_arn" {
  description = "ARN of the admin cleanup Lambda function"
  type        = string
}

variable "admin_cleanup_schedule" {
  description = "Schedule expression for admin instance cleanup"
  type        = string
  default     = "cron(0 2 ? * SUN *)"
}




