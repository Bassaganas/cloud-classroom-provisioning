terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "azurerm" {
  features {}
}

# AWS Infrastructure
module "aws_infrastructure" {
  count  = var.cloud_provider == "aws" ? 1 : 0
  source = "./aws"

  classroom_name = var.classroom_name
  student_count  = var.student_count
  environment    = var.environment
  owner          = var.owner
  region         = var.aws_region
}

# Azure Infrastructure
module "azure_infrastructure" {
  count  = var.cloud_provider == "azure" ? 1 : 0
  source = "./azure"

  classroom_name = var.classroom_name
  student_count  = var.student_count
  environment    = var.environment
  owner          = var.owner
  location       = var.azure_location
}
