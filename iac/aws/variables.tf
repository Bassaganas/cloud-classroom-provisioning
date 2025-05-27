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
  default     = "eu-west-1"
}

variable "classroom_name" {
  description = "The name of the classroom"
  type        = string
  default     = "conference-classroom"
}
