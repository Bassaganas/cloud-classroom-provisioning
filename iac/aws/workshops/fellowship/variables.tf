variable "environment" {
  description = "The environment name"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
  default     = "admin"
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
  default     = "eu-west-1"
}

variable "common_state_bucket" {
  description = "S3 bucket for the common Terraform state"
  type        = string
  default     = "terraform-state-classroom-shared"
}

variable "common_state_key" {
  description = "State key for the common Terraform state"
  type        = string
  default     = "classroom/shared/terraform.tfstate"
}

variable "common_state_region" {
  description = "Region for the common Terraform state"
  type        = string
  default     = "eu-west-3"
}

variable "common_state_dynamodb_table" {
  description = "DynamoDB table for the common Terraform state lock"
  type        = string
  default     = "terraform-locks-classroom-shared"
}

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
  default     = "fellowship-of-the-build"
}

variable "workshop_name" {
  description = "Workshop identifier for tagging and naming"
  type        = string
  default     = "fellowship_of_the_build"
}

# --- EC2 Pool for Classroom Assignment ---
# EMERGENCY OPTION: EC2 instances are normally created dynamically via the instance_manager Lambda function
# This variable allows creating instances via Terraform as an emergency option
# Default is 0 (instances created via Lambda). Set to > 0 to enable Terraform-created instances.
variable "ec2_pool_size" {
  description = "Emergency option: Number of EC2 instances to create via Terraform (default: 0). Normally, instances are created via the instance_manager Lambda UI at /ui"
  type        = number
  default     = 0
}

variable "ec2_ami_id" {
  description = "AMI ID for classroom EC2 instances."
  type        = string
  default     = "ami-0746ed6b6c0683e67"
}

variable "ec2_instance_type" {
  description = "Instance type for classroom EC2 instances."
  type        = string
  default     = "t3.medium"
}

variable "ec2_subnet_id" {
  description = "Subnet ID for classroom EC2 instances. Leave empty to auto-discover default subnet."
  type        = string
  default     = ""
}

variable "instance_stop_timeout_minutes" {
  description = "Number of minutes before an instance is considered idle and should be stopped"
  type        = number
  default     = 4
}

variable "instance_terminate_timeout_minutes" {
  description = "Number of minutes before a stopped instance should be terminated"
  type        = number
  default     = 20
}

variable "hard_terminate_timeout_minutes" {
  description = "Number of minutes before a stopped instance should be hard terminated"
  type        = number
  default     = 45
}

variable "admin_cleanup_interval_days" {
  description = "Number of days after which admin instances should be automatically deleted (default: 7 for weekly cleanup)"
  type        = number
  default     = 7
}

variable "admin_cleanup_schedule" {
  description = "Schedule expression for admin instance cleanup (default: weekly on Sunday at 2 AM UTC)"
  type        = string
  default     = "cron(0 2 ? * SUN *)"  # Weekly on Sunday at 2 AM UTC
}

variable "instance_manager_password" {
  description = "Password for instance manager authentication (leave empty to auto-generate a secure password)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "skip_iam_user_creation" {
  description = "Skip IAM user creation to avoid rate limiting (useful for conference scenarios). When true, users will only get EC2 instances, not AWS console access."
  type        = bool
  default     = false
}

# Lambda Scaling and Performance Configuration
variable "user_management_memory_size" {
  description = "Memory size (MB) for user_management Lambda. More memory = more CPU. Range: 128-10240 MB. Default: 512 MB (increased from 256 for better performance)"
  type        = number
  default     = 512
}

variable "user_management_timeout" {
  description = "Timeout (seconds) for user_management Lambda. Range: 1-900 seconds. Default: 120 seconds (increased from 60 for conference scenarios)"
  type        = number
  default     = 120
}

variable "user_management_provisioned_concurrency" {
  description = "Number of provisioned concurrent executions for user_management Lambda. Eliminates cold starts but costs more. Set to 0 to disable. Recommended: 10-50 for conference scenarios (100 users). Default: 0"
  type        = number
  default     = 0
}

variable "user_management_reserved_concurrency" {
  description = "Reserved concurrency for user_management Lambda. Guarantees capacity but limits scaling. Set to 0 to use unreserved concurrency. Recommended: 0 (unlimited) unless you need to protect other functions. Default: 0"
  type        = number
  default     = 0
}

variable "instance_manager_memory_size" {
  description = "Memory size (MB) for instance_manager Lambda. Default: 512 MB"
  type        = number
  default     = 512
}

variable "instance_manager_timeout" {
  description = "Timeout (seconds) for instance_manager Lambda. Default: 300 seconds"
  type        = number
  default     = 300
}
