variable "zone_name" {
  description = "Override for the Route53 hosted zone name. If empty, derived from domain_name by stripping the first label. Use this when domain_name has more than 3 parts (e.g. docs.fellowship.testingfantasy.com)."
  type        = string
  default     = ""
}

variable "enable_s3_path_rewrite" {
  description = "Enable a CloudFront viewer-request Function that rewrites directory-style paths to append /index.html. Required for Docusaurus SSG served from a private S3 bucket via OAI (CloudFront REST API does not auto-serve index.html for sub-directories)."
  type        = bool
  default     = false
}

variable "s3_origin_access_control_id" {
  description = "CloudFront Origin Access Control (OAC) ID for S3 origin. When set, OAC is used instead of the legacy OAI. The S3 origin domain will automatically use the regional endpoint required by OAC."
  type        = string
  default     = ""
}

# S3 origin bucket for static site (docs)
variable "s3_origin_bucket" {
  description = "Name of the S3 bucket to use as the CloudFront origin for static site (docs)"
  type        = string
  default     = ""
}
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

variable "domain_name" {
  description = "Custom domain name for CloudFront distribution"
  type        = string
}

variable "lambda_function_url" {
  description = "Lambda Function URL to use as origin for API (deprecated - use api_gateway_domain instead)"
  type        = string
  default     = ""
}

variable "api_gateway_domain" {
  description = "API Gateway domain name to use as origin for API. Can be either the regional endpoint (e.g., {api-id}.execute-api.{region}.amazonaws.com) or a custom domain (e.g., ec2-management-api.testingfantasy.com). If using custom domain, path rewriting is not needed."
  type        = string
  default     = ""
}

variable "use_api_gateway_custom_domain" {
  description = "Whether the api_gateway_domain is a custom domain. If true, CloudFront Function path rewriting will be disabled."
  type        = bool
  default     = false
}

variable "api_gateway_path" {
  description = "API Gateway stage path (e.g., /dev, /prod). Not needed when using API Gateway stages - stage is part of the domain URL structure. Leave empty to forward paths directly to API Gateway."
  type        = string
  default     = ""
}

variable "s3_bucket_domain" {
  description = "S3 bucket regional domain name for frontend"
  type        = string
  default     = ""
}

variable "s3_origin_access_identity" {
  description = "CloudFront Origin Access Identity path for S3"
  type        = string
  default     = ""
}

variable "wait_for_certificate_validation" {
  description = "Whether to wait for certificate validation to complete (set to false if DNS records not added yet)"
  type        = bool
  default     = true
}

variable "enable_route53_records" {
  description = "Whether this module should create/read Route53 records for certificate validation and aliases"
  type        = bool
  default     = true
}

variable "enable_cloudwatch_logging" {
  description = "Enable CloudWatch logging for CloudFront distribution"
  type        = bool
  default     = true
}

variable "cloudwatch_log_retention_days" {
  description = "Number of days to retain CloudFront logs in CloudWatch"
  type        = number
  default     = 30
}

variable "cloudfront_log_sampling_rate" {
  description = "Sampling rate for CloudFront real-time logs (0-100)"
  type        = number
  default     = 100
  validation {
    condition     = var.cloudfront_log_sampling_rate >= 0 && var.cloudfront_log_sampling_rate <= 100
    error_message = "Sampling rate must be between 0 and 100."
  }
}

variable "kinesis_shard_count" {
  description = "Number of shards for Kinesis stream (affects throughput and cost)"
  type        = number
  default     = 1
}

variable "kinesis_retention_hours" {
  description = "Data retention period for Kinesis stream in hours (24-168)"
  type        = number
  default     = 24
  validation {
    condition     = var.kinesis_retention_hours >= 24 && var.kinesis_retention_hours <= 168
    error_message = "Kinesis retention must be between 24 and 168 hours."
  }
}


