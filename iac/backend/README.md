# Terraform Backend Setup

This directory contains the configuration for setting up Terraform backend resources for both AWS and Azure.

## AWS Backend

The AWS backend uses:
- S3 bucket for storing Terraform state files
- DynamoDB table for state locking
- Server-side encryption enabled
- Versioning enabled
- Public access blocked

### Setup Steps

1. Navigate to the AWS backend directory:
   ```bash
   cd aws
   ```

2. Copy the example variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

3. Edit `terraform.tfvars` with your desired values:
   ```hcl
   aws_region         = "eu-west-1"
   state_bucket_name  = "my-terraform-state-bucket"
   dynamodb_table_name = "my-terraform-locks"
   ```

4. Initialize and apply:
   ```bash
   terraform init
   terraform apply
   ```

5. Use the backend in your Terraform configurations:
   ```hcl
   terraform {
     backend "s3" {
       bucket         = "my-terraform-state-bucket"
       key            = "path/to/terraform.tfstate"
       region         = "eu-west-1"
       dynamodb_table = "my-terraform-locks"
       encrypt        = true
     }
   }
   ```

## Azure Backend

The Azure backend uses:
- Storage Account for storing Terraform state files
- Blob container for state files
- Key Vault for storing sensitive values
- Versioning enabled
- Private access only

### Setup Steps

1. Navigate to the Azure backend directory:
   ```bash
   cd azure
   ```

2. Copy the example variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

3. Edit `terraform.tfvars` with your desired values:
   ```hcl
   resource_group_name  = "terraform-state-rg"
   location           = "westeurope"
   storage_account_name = "tfstateaccount"
   key_vault_name     = "tfstate-kv"
   ```

4. Initialize and apply:
   ```bash
   terraform init
   terraform apply
   ```

5. Use the backend in your Terraform configurations:
   ```hcl
   terraform {
     backend "azurerm" {
       resource_group_name  = "terraform-state-rg"
       storage_account_name = "tfstateaccount"
       container_name      = "tfstate"
       key                 = "path/to/terraform.tfstate"
     }
   }
   ```

## Important Notes

1. The backend resources should be created before using them in other Terraform configurations.
2. Make sure to keep the backend state files secure and backed up.
3. The S3 bucket and Storage Account names must be globally unique.
4. Consider using different backend configurations for different environments (dev, staging, prod). 