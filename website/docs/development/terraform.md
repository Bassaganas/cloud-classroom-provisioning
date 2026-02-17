---
sidebar_position: 1
---

# Terraform Structure

## Directory Organization

```
iac/
├── aws/                          # AWS Infrastructure (Root Module)
│   ├── main.tf                   # Root module (includes common + workshops)
│   ├── backend.tf                # Terraform backend configuration
│   ├── variables.tf              # Root variables
│   ├── outputs.tf                # Aggregate outputs
│   ├── terraform.tfvars          # Configuration values
│   ├── modules/                  # Reusable Terraform modules
│   │   ├── common/               # Common infrastructure module
│   │   │   ├── main.tf           # Module definition
│   │   │   ├── variables.tf      # Module inputs
│   │   │   ├── outputs.tf        # Module outputs
│   │   │   └── ...               # Other module files
│   │   ├── workshop/             # Parameterized workshop module
│   │   ├── compute/              # EC2 and security groups
│   │   ├── storage/              # DynamoDB, SSM, Secrets Manager
│   │   ├── lambda/               # Lambda functions
│   │   ├── api-gateway/          # API Gateway configuration
│   │   ├── cloudfront/           # CloudFront distributions
│   │   ├── s3/                   # S3 buckets
│   │   ├── iam/                  # IAM roles and policies
│   │   ├── iam-lambda/           # Lambda execution roles
│   │   └── monitoring/           # EventBridge rules
│   └── workshops/                # Workshop-specific files
│       ├── fellowship/
│       │   └── user_data.sh      # EC2 user data script
│       └── testus_patronus/
│           └── user_data.sh      # EC2 user data script
├── backend/                      # Terraform Backend Setup
│   ├── aws/                      # AWS backend (S3 + DynamoDB)
│   │   ├── main.tf               # Backend resources
│   │   ├── variables.tf          # Backend configuration
│   │   └── terraform.tfvars.example
│   └── azure/                    # Azure backend
└── azure/                        # Azure Infrastructure
```

## Root Module Structure

The `iac/aws/main.tf` file orchestrates all infrastructure:

```hcl
# Common Infrastructure Module
module "common" {
  source = "./modules/common"
  # ... common infrastructure variables
}

# Fellowship Workshop Module
module "workshop_fellowship" {
  source = "./modules/workshop"
  depends_on = [module.common]
  # ... fellowship-specific variables
}

# Testus Patronus Workshop Module
module "workshop_testus_patronus" {
  source = "./modules/workshop"
  depends_on = [module.common]
  # ... testus_patronus-specific variables
}
```

## Module Organization

### Common Module (`modules/common/`)
- EC2 Instance Manager (Lambda, API Gateway, CloudFront)
- Shared S3 bucket for frontend
- Common security groups and IAM roles
- Shared DynamoDB tables and SSM parameters

### Workshop Module (`modules/workshop/`)
- User Management Lambda function
- Status checking Lambda function
- Workshop-specific CloudFront distributions
- Workshop-specific DynamoDB tables
- Workshop-specific SSM parameters

### Reusable Modules
- `compute/`: EC2 instances, security groups, instance profiles
- `storage/`: DynamoDB tables, SSM parameters, Secrets Manager
- `lambda/`: Lambda function definitions
- `api-gateway/`: API Gateway REST API configuration
- `cloudfront/`: CloudFront distributions and functions
- `s3/`: S3 bucket configuration
- `iam/`: IAM roles and policies
- `monitoring/`: EventBridge scheduled rules

## Backend Configuration

Terraform state is stored remotely in S3:

```hcl
terraform {
  backend "s3" {
    bucket         = "terraform-state-classroom-shared-{region}"
    key            = "classroom/{environment}/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-locks-classroom-shared"
    encrypt        = true
  }
}
```

**State Management:**
- Separate state files per environment: `classroom/dev/terraform.tfstate`, `classroom/staging/terraform.tfstate`
- State locking via DynamoDB prevents concurrent modifications
- Versioning enabled for state file history

## Variable Configuration

**Root Variables** (`iac/aws/variables.tf`):
- Environment configuration (dev, staging, prod)
- Region and domain settings
- Workshop-specific configurations
- EC2 instance types and pool sizes
- Timeout settings

**Configuration File** (`iac/aws/terraform.tfvars`):
```hcl
environment = "dev"
owner       = "admin"
region      = "eu-west-1"
```

## Outputs

**Root Outputs** (`iac/aws/outputs.tf`):
- Instance Manager URLs (Lambda, API Gateway, CloudFront)
- Workshop-specific Lambda URLs
- S3 bucket names
- Security group IDs
- Template configurations

**Access Outputs:**
```bash
cd iac/aws
terraform output instance_manager_url
terraform output instance_manager_custom_url
terraform output testus_patronus_lambda_function_url
```
