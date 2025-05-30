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

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
  default     = "testus-patronus"
}

# --- EC2 Pool for Classroom Assignment ---
variable "ec2_pool_size" {
  description = "Number of EC2 instances to pre-provision in the pool."
  type        = number
  default     = 30
}

variable "ec2_ami_id" {
  description = "AMI ID for classroom EC2 instances."
  type        = string
  default     = "ami-0746ed6b6c0683e67"
}

variable "ec2_instance_type" {
  description = "Instance type for classroom EC2 instances."
  type        = string
  default     = "m5.large"
}

variable "ec2_subnet_id" {
  description = "Subnet ID for classroom EC2 instances."
  type        = string
  default     = "subnet-076c4fca18acc0b7e"
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