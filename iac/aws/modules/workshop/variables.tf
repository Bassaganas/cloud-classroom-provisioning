# Common infrastructure outputs (passed from root module)
variable "common_subnet_id" {
  description = "Subnet ID from common infrastructure"
  type        = string
}

variable "common_security_group_ids" {
  description = "Security group IDs from common infrastructure"
  type        = list(string)
}

variable "common_ec2_iam_instance_profile_name" {
  description = "EC2 IAM instance profile name from common infrastructure"
  type        = string
}

variable "common_ec2_iam_role_arn" {
  description = "EC2 IAM role ARN from common infrastructure (for attaching S3 policies)"
  type        = string
  default     = ""
}

variable "common_instance_manager_password_secret_name" {
  description = "Instance manager password secret name from common infrastructure"
  type        = string
}

variable "common_instance_manager_password_secret_arn" {
  description = "Instance manager password secret ARN from common infrastructure"
  type        = string
}

# Workshop-specific variables
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
  default     = "eu-west-3"
}

variable "workshop_name" {
  description = "Workshop identifier for tagging and naming"
  type        = string
}

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
}

variable "ec2_ami_id" {
  description = "AMI ID for classroom EC2 instances. If empty, will use latest Amazon Linux 2 AMI for the region"
  type        = string
  default     = ""
}

variable "ec2_instance_type" {
  description = "Instance type for classroom EC2 instances"
  type        = string
  default     = "t3.medium"
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
  description = "Number of days after which admin instances should be automatically deleted"
  type        = number
  default     = 7
}

variable "admin_cleanup_schedule" {
  description = "Schedule expression for admin instance cleanup"
  type        = string
  default     = "cron(0 2 ? * SUN *)"
}

variable "instance_manager_password" {
  description = "Password for instance manager authentication (leave empty to auto-generate)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "skip_iam_user_creation" {
  description = "Skip IAM user creation to avoid rate limiting"
  type        = bool
  default     = false
}

# Lambda scaling and performance configuration
variable "user_management_memory_size" {
  description = "Memory size (MB) for user_management Lambda"
  type        = number
  default     = 512
}

variable "user_management_timeout" {
  description = "Timeout (seconds) for user_management Lambda"
  type        = number
  default     = 120
}

variable "user_management_provisioned_concurrency" {
  description = "Number of provisioned concurrent executions for user_management Lambda"
  type        = number
  default     = 0
}

variable "user_management_reserved_concurrency" {
  description = "Reserved concurrency for user_management Lambda"
  type        = number
  default     = 0
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

# CloudFront domain configuration
variable "user_management_domain" {
  description = "Domain name for user management CloudFront distribution"
  type        = string
}

variable "dify_jira_domain" {
  description = "Domain name for Dify Jira API CloudFront distribution"
  type        = string
}

variable "wait_for_certificate_validation" {
  description = "Wait for ACM certificate validation before creating CloudFront distribution"
  type        = bool
  default     = true
}

# Security group rules (optional, for workshop-specific ports like Jenkins, MailHog)
variable "security_group_rules" {
  description = "Map of additional security group ingress rules (e.g., for Jenkins, MailHog)"
  type = map(object({
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    description = string
  }))
  default = {}
}
# Spot instance configuration
variable "enable_spot_instances" {
  description = "Enable EC2 Spot Instance support with capacity reservation blocks"
  type        = bool
  default     = true
}

variable "spot_default_duration_minutes" {
  description = "Default spot instance reservation duration in minutes (60-360, i.e., 1-6 hours)"
  type        = number
  default     = 120
  validation {
    condition     = var.spot_default_duration_minutes >= 60 && var.spot_default_duration_minutes <= 360
    error_message = "Spot duration must be between 60 and 360 minutes (1-6 hours)."
  }
}

variable "spot_max_price_multiplier" {
  description = "Multiplier for on-demand price to set as max spot price (e.g., 0.9 for 90% of on-demand)"
  type        = number
  default     = 1.0
  validation {
    condition     = var.spot_max_price_multiplier > 0 && var.spot_max_price_multiplier <= 1.0
    error_message = "Spot max price multiplier must be between 0.01 and 1.0."
  }
}