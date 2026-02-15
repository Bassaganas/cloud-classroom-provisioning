# Root-level variables for consolidated infrastructure

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

# Common infrastructure variables
variable "common_workshop_name" {
  description = "Workshop identifier for shared EC2 manager resources"
  type        = string
  default     = "shared"
}

variable "common_classroom_name" {
  description = "Classroom name used for Lambda naming"
  type        = string
  default     = "common"
}

variable "common_ec2_pool_size" {
  description = "Emergency option: Number of EC2 instances to create via Terraform"
  type        = number
  default     = 0
}

variable "common_ec2_ami_id" {
  description = "AMI ID for classroom EC2 instances. If empty, will use latest Amazon Linux 2 AMI for the region"
  type        = string
  default     = ""
}

variable "common_ec2_instance_type" {
  description = "Instance type for classroom EC2 instances"
  type        = string
  default     = "t3.micro"
}

variable "common_ec2_subnet_id" {
  description = "Subnet ID for classroom EC2 instances"
  type        = string
  default     = ""
}

variable "common_instance_stop_timeout_minutes" {
  description = "Number of minutes before an instance is considered idle and should be stopped"
  type        = number
  default     = 4
}

variable "common_instance_terminate_timeout_minutes" {
  description = "Number of minutes before a stopped instance should be terminated"
  type        = number
  default     = 20
}

variable "common_hard_terminate_timeout_minutes" {
  description = "Number of minutes before a stopped instance should be hard terminated"
  type        = number
  default     = 45
}

variable "common_admin_cleanup_interval_days" {
  description = "Number of days after which admin instances should be automatically deleted"
  type        = number
  default     = 7
}

variable "common_admin_cleanup_schedule" {
  description = "Schedule expression for admin instance cleanup"
  type        = string
  default     = "cron(0 2 ? * SUN *)"
}

variable "common_instance_manager_password" {
  description = "Password for instance manager authentication (leave empty to auto-generate)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "common_instance_manager_memory_size" {
  description = "Memory size (MB) for instance_manager Lambda"
  type        = number
  default     = 512
}

variable "common_instance_manager_timeout" {
  description = "Timeout (seconds) for instance_manager Lambda"
  type        = number
  default     = 300
}

# Fellowship workshop variables
variable "fellowship_workshop_name" {
  description = "Workshop identifier for fellowship"
  type        = string
  default     = "fellowship"
}

variable "fellowship_classroom_name" {
  description = "Classroom name for fellowship"
  type        = string
  default     = "fellowship-of-the-build"
}

variable "fellowship_ec2_ami_id" {
  description = "AMI ID for fellowship EC2 instances. If empty, will use latest Amazon Linux 2 AMI for the region"
  type        = string
  default     = ""
}

variable "fellowship_ec2_instance_type" {
  description = "Instance type for fellowship EC2 instances"
  type        = string
  default     = "t3.small"
}

variable "fellowship_instance_stop_timeout_minutes" {
  description = "Instance stop timeout for fellowship"
  type        = number
  default     = 4
}

variable "fellowship_instance_terminate_timeout_minutes" {
  description = "Instance terminate timeout for fellowship"
  type        = number
  default     = 20
}

variable "fellowship_hard_terminate_timeout_minutes" {
  description = "Hard terminate timeout for fellowship"
  type        = number
  default     = 45
}

variable "fellowship_admin_cleanup_interval_days" {
  description = "Admin cleanup interval for fellowship"
  type        = number
  default     = 7
}

variable "fellowship_admin_cleanup_schedule" {
  description = "Admin cleanup schedule for fellowship"
  type        = string
  default     = "cron(0 2 ? * SUN *)"
}

variable "fellowship_instance_manager_password" {
  description = "Instance manager password for fellowship"
  type        = string
  default     = ""
  sensitive   = true
}

variable "fellowship_skip_iam_user_creation" {
  description = "Skip IAM user creation for fellowship"
  type        = bool
  default     = false
}

variable "fellowship_user_management_memory_size" {
  description = "User management memory size for fellowship"
  type        = number
  default     = 512
}

variable "fellowship_user_management_timeout" {
  description = "User management timeout for fellowship"
  type        = number
  default     = 120
}

variable "fellowship_user_management_provisioned_concurrency" {
  description = "User management provisioned concurrency for fellowship"
  type        = number
  default     = 0
}

variable "fellowship_user_management_reserved_concurrency" {
  description = "User management reserved concurrency for fellowship"
  type        = number
  default     = 0
}

variable "fellowship_instance_manager_memory_size" {
  description = "Instance manager memory size for fellowship"
  type        = number
  default     = 512
}

variable "fellowship_instance_manager_timeout" {
  description = "Instance manager timeout for fellowship"
  type        = number
  default     = 300
}

variable "fellowship_user_management_domain" {
  description = "User management domain for fellowship"
  type        = string
  default     = "fellowship-of-the-build.testingfantasy.com"
}

variable "fellowship_dify_jira_domain" {
  description = "Dify Jira domain for fellowship"
  type        = string
  default     = "dify-jira-fellowship.testingfantasy.com"
}

variable "fellowship_wait_for_certificate_validation" {
  description = "Wait for certificate validation for fellowship"
  type        = bool
  default     = false
}

# Testus Patronus workshop variables
variable "testus_patronus_workshop_name" {
  description = "Workshop identifier for testus_patronus"
  type        = string
  default     = "testus_patronus"
}

variable "testus_patronus_classroom_name" {
  description = "Classroom name for testus_patronus"
  type        = string
  default     = "testus-patronus"
}

variable "testus_patronus_ec2_ami_id" {
  description = "AMI ID for testus_patronus EC2 instances. If empty, will use latest Amazon Linux 2 AMI for the region"
  type        = string
  default     = ""
}

variable "testus_patronus_ec2_instance_type" {
  description = "Instance type for testus_patronus EC2 instances"
  type        = string
  default     = "t3.small"
}

variable "testus_patronus_instance_stop_timeout_minutes" {
  description = "Instance stop timeout for testus_patronus"
  type        = number
  default     = 4
}

variable "testus_patronus_instance_terminate_timeout_minutes" {
  description = "Instance terminate timeout for testus_patronus"
  type        = number
  default     = 20
}

variable "testus_patronus_hard_terminate_timeout_minutes" {
  description = "Hard terminate timeout for testus_patronus"
  type        = number
  default     = 45
}

variable "testus_patronus_admin_cleanup_interval_days" {
  description = "Admin cleanup interval for testus_patronus"
  type        = number
  default     = 7
}

variable "testus_patronus_admin_cleanup_schedule" {
  description = "Admin cleanup schedule for testus_patronus"
  type        = string
  default     = "cron(0 2 ? * SUN *)"
}

variable "testus_patronus_instance_manager_password" {
  description = "Instance manager password for testus_patronus"
  type        = string
  default     = ""
  sensitive   = true
}

variable "testus_patronus_skip_iam_user_creation" {
  description = "Skip IAM user creation for testus_patronus"
  type        = bool
  default     = false
}

variable "testus_patronus_user_management_memory_size" {
  description = "User management memory size for testus_patronus"
  type        = number
  default     = 512
}

variable "testus_patronus_user_management_timeout" {
  description = "User management timeout for testus_patronus"
  type        = number
  default     = 120
}

variable "testus_patronus_user_management_provisioned_concurrency" {
  description = "User management provisioned concurrency for testus_patronus"
  type        = number
  default     = 0
}

variable "testus_patronus_user_management_reserved_concurrency" {
  description = "User management reserved concurrency for testus_patronus"
  type        = number
  default     = 0
}

variable "testus_patronus_instance_manager_memory_size" {
  description = "Instance manager memory size for testus_patronus"
  type        = number
  default     = 512
}

variable "testus_patronus_instance_manager_timeout" {
  description = "Instance manager timeout for testus_patronus"
  type        = number
  default     = 300
}

variable "testus_patronus_user_management_domain" {
  description = "User management domain for testus_patronus"
  type        = string
  default     = "testus-patronus.testingfantasy.com"
}

variable "testus_patronus_dify_jira_domain" {
  description = "Dify Jira domain for testus_patronus"
  type        = string
  default     = "dify-jira.testingfantasy.com"
}

variable "testus_patronus_wait_for_certificate_validation" {
  description = "Wait for certificate validation for testus_patronus"
  type        = bool
  default     = true
}
