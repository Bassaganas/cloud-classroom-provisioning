variable "lambda_function_arn" {
  description = "ARN of the Lambda function to integrate with API Gateway"
  type        = string
}

variable "environment" {
  description = "The environment name"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "workshop_name" {
  description = "Workshop identifier for tagging"
  type        = string
}

variable "domain_name" {
  description = "Custom domain name (for documentation purposes)"
  type        = string
  default     = ""
}

variable "api_custom_domain_name" {
  description = "Custom domain name for API Gateway (e.g., ec2-management-api.testingfantasy.com). If empty, custom domain will not be created."
  type        = string
  default     = ""
}

variable "base_domain" {
  description = "Base domain for Route53 hosted zone lookup (e.g., testingfantasy.com)"
  type        = string
  default     = ""
}

variable "wait_for_certificate_validation" {
  description = "Wait for ACM certificate validation before creating custom domain. Set to true only after DNS validation records are added."
  type        = bool
  default     = false
}

variable "enable_logging" {
  description = "Enable CloudWatch logging for API Gateway stage"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
}
