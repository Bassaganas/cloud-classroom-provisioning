variable "environment" {
  description = "The environment name"
  type        = string
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "domain_name" {
  description = "Root domain name for the static website"
  type        = string
}

variable "wait_for_certificate_validation" {
  description = "Whether to wait for certificate validation to complete"
  type        = bool
  default     = false
}

