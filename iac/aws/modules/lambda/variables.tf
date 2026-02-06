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

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
}

variable "enable_status" {
  description = "Whether to create the status Lambda"
  type        = bool
  default     = true
}

variable "enable_user_management" {
  description = "Whether to create the user management Lambda"
  type        = bool
  default     = true
}

variable "enable_instance_manager" {
  description = "Whether to create the instance manager Lambda"
  type        = bool
  default     = true
}

variable "enable_stop_old_instances" {
  description = "Whether to create the stop old instances Lambda"
  type        = bool
  default     = true
}

variable "enable_admin_cleanup" {
  description = "Whether to create the admin cleanup Lambda"
  type        = bool
  default     = true
}

variable "enable_dify_jira_api" {
  description = "Whether to create the Dify Jira API Lambda"
  type        = bool
  default     = true
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

variable "skip_iam_user_creation" {
  description = "Skip IAM user creation to avoid rate limiting (useful for conference scenarios). When true, users will only get EC2 instances, not AWS console access."
  type        = bool
  default     = true
}

# Lambda Scaling and Performance Variables
variable "user_management_memory_size" {
  description = "Memory size (MB) for user_management Lambda. More memory = more CPU. Range: 128-10240 MB"
  type        = number
  default     = 512  # Increased from 256 for better performance
}

variable "user_management_timeout" {
  description = "Timeout (seconds) for user_management Lambda. Range: 1-900 seconds"
  type        = number
  default     = 120  # Increased from 60 for conference scenarios
}

variable "user_management_provisioned_concurrency" {
  description = "Number of provisioned concurrent executions for user_management Lambda. Eliminates cold starts but costs more. Set to 0 to disable."
  type        = number
  default     = 0  # Disabled by default (cost optimization)
}

variable "user_management_reserved_concurrency" {
  description = "Reserved concurrency for user_management Lambda. Guarantees capacity but limits scaling. Set to 0 to use unreserved concurrency."
  type        = number
  default     = 0  # No reservation by default (allows full scaling)
}

variable "instance_manager_memory_size" {
  description = "Memory size (MB) for instance_manager Lambda"
  type        = number
  default     = 512
}

variable "instance_manager_timeout" {
  description = "Timeout (seconds) for instance_manager Lambda"
  type        = number
  default     = 300
}

