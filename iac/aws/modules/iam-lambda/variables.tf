variable "environment" {
  description = "The environment name"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "secrets_manager_secret_arn" {
  description = "ARN of the Secrets Manager secret for Azure LLM configs (optional)"
  type        = string
  default     = ""
}

variable "instance_manager_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for instance manager password (optional)"
  type        = string
  default     = ""
}

variable "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret for instance manager password (optional, used for count check)"
  type        = string
  default     = ""
}
