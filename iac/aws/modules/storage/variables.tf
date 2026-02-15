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

variable "instance_stop_timeout_minutes" {
  description = "Timeout in minutes before stopping unassigned running instances"
  type        = number
  default     = 60
}

variable "instance_terminate_timeout_minutes" {
  description = "Timeout in minutes before terminating stopped instances"
  type        = number
  default     = 20
}

variable "instance_hard_terminate_timeout_minutes" {
  description = "Timeout in minutes before hard terminating any instance"
  type        = number
  default     = 240
}

variable "instance_manager_password" {
  description = "Password for instance manager authentication (leave empty to auto-generate)"
  type        = string
  default     = ""
  sensitive   = true
}




variable "create_instance_manager_password_secret" {
  description = "Whether to create the instance manager password secret (set to false if using a shared/common secret)"
  type        = bool
  default     = true
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
}
