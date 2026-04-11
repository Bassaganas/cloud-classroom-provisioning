variable "environment" {
  description = "The environment name (dev, staging, prod)"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "workshop_name" {
  description = "Workshop identifier used in resource naming and tagging"
  type        = string
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
}

variable "ec2_iam_role_arn" {
  description = "ARN of the EC2 IAM role allowed to publish to this queue (producer)"
  type        = string
}

variable "lambda_artifact_bucket" {
  description = "S3 bucket name holding the leaderboard Lambda deployment artifact"
  type        = string
  default     = ""

  validation {
    condition     = trimspace(var.lambda_artifact_bucket) == "" || length(trimspace(var.lambda_artifact_bucket)) >= 3
    error_message = "lambda_artifact_bucket must be empty (to use local packaged artifact) or a valid S3 bucket name with at least 3 characters."
  }
}

variable "lambda_artifact_key" {
  description = "S3 key (path) of the leaderboard Lambda deployment zip artifact"
  type        = string
  default     = "palantir/leaderboard_lambda.zip"
}
