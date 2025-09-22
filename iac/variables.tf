variable "cloud_provider" {
  description = "The cloud provider to use (aws or azure)"
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["aws", "azure"], var.cloud_provider)
    error_message = "The cloud_provider value must be either 'aws' or 'azure'."
  }
}

variable "classroom_name" {
  description = "Name of the classroom"
  type        = string
}

variable "student_count" {
  description = "Number of students in the classroom"
  type        = number
  default     = 1
}

variable "environment" {
  description = "Environment name (e.g., dev, test, prod)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner of the resources"
  type        = string
}

variable "aws_region" {
  description = "The AWS region to deploy to"
  type        = string
  default     = "eu-west-1"
}

variable "azure_location" {
  description = "The Azure location to deploy to"
  type        = string
  default     = "westeurope"
} 
