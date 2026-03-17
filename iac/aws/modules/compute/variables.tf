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

variable "ec2_pool_size" {
  description = "Emergency option: Number of EC2 instances to create via Terraform (default: 0)"
  type        = number
  default     = 0
}

variable "ec2_ami_id" {
  description = "AMI ID for classroom EC2 instances"
  type        = string
}

variable "ec2_instance_type" {
  description = "Instance type for classroom EC2 instances"
  type        = string
}

variable "ec2_subnet_id" {
  description = "Subnet ID for classroom EC2 instances"
  type        = string
}

variable "user_data_script_path" {
  description = "Path to the user_data.sh script"
  type        = string
  default     = ""
}

variable "user_data_script_content" {
  description = "Content of the user_data.sh script (alternative to path)"
  type        = string
  default     = ""
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
}

variable "sut_bucket_arn" {
  description = "ARN of the S3 bucket for Fellowship SUT (optional, only for fellowship workshop)"
  type        = string
  default     = ""
}

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




