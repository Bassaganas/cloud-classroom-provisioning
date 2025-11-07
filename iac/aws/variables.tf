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

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
  default     = "testus-patronus"
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
