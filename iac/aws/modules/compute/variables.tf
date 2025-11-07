variable "environment" {
  description = "The environment name"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
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




