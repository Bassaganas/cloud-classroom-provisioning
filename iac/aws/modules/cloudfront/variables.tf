variable "environment" {
  description = "The environment name"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "domain_name" {
  description = "Custom domain name for CloudFront distribution"
  type        = string
}

variable "lambda_function_url" {
  description = "Lambda Function URL to use as origin"
  type        = string
}

variable "wait_for_certificate_validation" {
  description = "Whether to wait for certificate validation to complete (set to false if DNS records not added yet)"
  type        = bool
  default      = true
}


