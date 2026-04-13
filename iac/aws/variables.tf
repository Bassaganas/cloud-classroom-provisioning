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

variable "enable_docs_dns_records" {
  description = "Whether to create Route53 records and certificate validation records for docs CloudFront"
  type        = bool
  default     = false
}

variable "github_actions_oidc_thumbprint" {
  description = "Thumbprint for the GitHub Actions OIDC provider"
  type        = string
  default     = "6938fd4d98bab03faadb97b34396831e3780aea1"
}

variable "shared_core_environment" {
  description = "Environment key used for shared-core SSM and Secrets Manager paths"
  type        = string
  default     = "prod"
}

variable "shared_core_github_owner" {
  description = "GitHub organisation or user that owns the repository running the shared-core deploy workflow"
  type        = string
  default     = "Bassaganas"
}

variable "shared_core_github_repo" {
  description = "GitHub repository name running the shared-core deploy workflow"
  type        = string
  default     = "lotr_sut"
}

variable "shared_core_github_environment" {
  description = "GitHub Actions environment name allowed to assume the shared-core OIDC role"
  type        = string
  default     = "sut-production"
}

variable "shared_core_ami_id" {
  description = "AMI ID for the shared-core EC2 host. If empty, latest Amazon Linux 2 AMI is used"
  type        = string
  default     = ""
}

variable "shared_core_instance_type" {
  description = "EC2 instance type for the shared-core Jenkins and Gitea host"
  type        = string
  default     = "t3.medium"
}

variable "shared_core_subnet_id" {
  description = "Subnet ID for the shared-core EC2 host. If empty, common module subnet is used"
  type        = string
  default     = ""
}

variable "shared_core_key_name" {
  description = "EC2 key pair name used for SSH access to the shared-core host"
  type        = string
  default     = ""
}

variable "shared_core_ssh_host" {
  description = "Optional override for shared-core SSH host. If empty, Terraform uses Jenkins domain when set, otherwise shared-core host public DNS/IP"
  type        = string
  default     = ""
}

variable "shared_core_mode" {
  description = "Enable shared-core mode: instance_manager issues shared Jenkins/Gitea URLs instead of per-student installs"
  type        = bool
  default     = true
}

variable "shared_core_jenkins_domain" {
  description = "Public Jenkins domain for shared core"
  type        = string
  default     = ""
}

variable "shared_core_gitea_domain" {
  description = "Public Gitea domain for shared core"
  type        = string
  default     = ""
}

variable "shared_core_manage_route53_records" {
  description = "Whether to manage Route53 records for shared-core Jenkins/Gitea domains"
  type        = bool
  default     = true
}

variable "shared_core_hosted_zone_id" {
  description = "Route53 hosted zone ID for shared-core Jenkins and Gitea records. When set, passed directly to shared-core-config to avoid a count-depends-on-computed-value Terraform error."
  type        = string
  default     = ""
}

variable "shared_core_security_group_id" {
  description = "Security group ID of the shared core instance"
  type        = string
  default     = ""
}

variable "shared_core_gitea_admin_user" {
  description = "Gitea admin username for shared core"
  type        = string
  default     = "fellowship"
}

variable "shared_core_gitea_admin_email" {
  description = "Gitea admin email for shared core"
  type        = string
  default     = "gandalf@fellowship.local"
}

variable "shared_core_gitea_org_name" {
  description = "Gitea organisation name for shared core"
  type        = string
  default     = "fellowship-org"
}

variable "shared_core_ssh_private_key" {
  description = "SSH private key used by the shared-core deploy workflow"
  type        = string
  default     = ""
  sensitive   = true
}

variable "shared_core_gh_repo_token" {
  description = "GitHub token used by the shared-core deploy workflow to clone the repository"
  type        = string
  default     = ""
  sensitive   = true
}

variable "shared_core_jenkins_admin_password" {
  description = "Jenkins admin password for the shared core stack"
  type        = string
  default     = ""
  sensitive   = true
}

variable "shared_core_gitea_admin_password" {
  description = "Gitea admin password for the shared core stack"
  type        = string
  default     = ""
  sensitive   = true
}

variable "manage_shared_core" {
  description = "When true, Terraform manages the shared-core EC2 instance, IAM role, Secrets Manager bundle, SSM config parameters, and ECS agent cluster. Set to false for automated dev CI runs so that the production shared-core is not touched."
  type        = bool
  default     = true
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

variable "fellowship_leaderboard_api_domain" {
  description = "Leaderboard API domain for fellowship"
  type        = string
  default     = "leaderboard-api-fellowship.testingfantasy.com"
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

variable "testus_patronus_leaderboard_api_domain" {
  description = "Leaderboard API domain for testus_patronus"
  type        = string
  default     = "leaderboard-api-testus-patronus.testingfantasy.com"
}

variable "testus_patronus_wait_for_certificate_validation" {
  description = "Wait for certificate validation for testus_patronus"
  type        = bool
  default     = true
}

# ── Palantir artifact variables (shared across workshops) ─────────────────────

variable "lambda_artifact_bucket" {
  description = "S3 bucket where the palantir leaderboard Lambda deployment artifact is stored"
  type        = string
  default     = ""

  validation {
    condition     = trimspace(var.lambda_artifact_bucket) == "" || length(trimspace(var.lambda_artifact_bucket)) >= 3
    error_message = "lambda_artifact_bucket must be empty (to use local packaged artifact) or a valid S3 bucket name with at least 3 characters."
  }
}

variable "lambda_artifact_key" {
  description = "S3 key of the leaderboard Lambda zip artifact uploaded by palantir-jenkins-ai CI"
  type        = string
  default     = "palantir/leaderboard_lambda.zip"
}

