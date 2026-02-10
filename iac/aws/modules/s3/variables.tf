variable "bucket_name" {
  description = "Name for the S3 bucket (will be suffixed with environment)"
  type        = string
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
