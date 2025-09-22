variable "environment" {
  description = "The environment name"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "The owner of the resources"
  type        = string
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
  default     = "eu-west-1"
} 
