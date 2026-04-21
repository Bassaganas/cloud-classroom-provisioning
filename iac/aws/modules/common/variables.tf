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

variable "base_domain" {
  description = "Base DNS domain for custom workshop subdomains"
  type        = string
  default     = "testingfantasy.com"
}

variable "workshop_name" {
  description = "Workshop identifier for shared EC2 manager resources"
  type        = string
  default     = "shared"
}

variable "classroom_name" {
  description = "Classroom name used for Lambda naming"
  type        = string
  default     = "common"
}

variable "ec2_pool_size" {
  description = "Emergency option: Number of EC2 instances to create via Terraform"
  type        = number
  default     = 0
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

variable "ec2_subnet_id" {
  description = "Subnet ID for classroom EC2 instances"
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

variable "shared_core_mode" {
  description = "Enable shared-core mode in instance_manager"
  type        = bool
  default     = true
}

variable "shared_core_jenkins_domain" {
  description = "Public Jenkins domain for shared core (used to build SHARED_JENKINS_URL)"
  type        = string
  default     = ""
}

variable "shared_core_gitea_domain" {
  description = "Public Gitea domain for shared core (used to build SHARED_GITEA_URL)"
  type        = string
  default     = ""
}

variable "sut_bucket_name" {
  description = "Name of the S3 SUT bucket (from the workshop s3-sut module output); passed to the shared-core-provisioner Lambda as SUT_BUCKET"
  type        = string
  default     = ""
}
