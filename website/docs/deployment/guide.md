---
sidebar_position: 1
---

# Deployment Guide

## Step-by-Step Deployment Process

The `setup_classroom.sh` script automates the entire deployment process:

1. **Backend Setup** (Automatic):
   - Creates S3 bucket for Terraform state: `terraform-state-classroom-shared-{region}`
   - Creates DynamoDB table for state locking: `terraform-locks-classroom-shared`
   - Enables encryption and versioning

2. **Lambda Packaging** (Automatic):
   - Packages Python Lambda functions with dependencies
   - Creates ZIP files in `functions/packages/`

3. **Infrastructure Deployment** (Automatic):
   - Deploys common infrastructure (EC2 manager, API Gateway, CloudFront)
   - Deploys workshop-specific infrastructure (user management, status functions)
   - Creates EC2 instance pool (if `--with-pool` specified)

4. **Frontend Deployment** (Automatic):
   - Builds React application
   - Uploads to S3 bucket
   - Invalidates CloudFront cache

## Deployment Options

### Environment Selection

```bash
# Deploy to dev environment (default)
./scripts/setup_classroom.sh --name my-class --cloud aws --environment dev

# Deploy to staging environment
./scripts/setup_classroom.sh --name my-class --cloud aws --environment staging

# Deploy to production environment
./scripts/setup_classroom.sh --name my-class --cloud aws --environment prod
```

### Partial Deployments

```bash
# Deploy only common infrastructure (EC2 manager)
./scripts/setup_classroom.sh --name my-class --cloud aws --only-common

# Deploy only workshop infrastructure
./scripts/setup_classroom.sh --name my-class --cloud aws --only-workshop
```

### Workshop Selection

```bash
# Deploy Testus Patronus workshop (default)
./scripts/setup_classroom.sh --name my-class --cloud aws --workshop testus_patronus

# Deploy Fellowship workshop
./scripts/setup_classroom.sh --name my-class --cloud aws --workshop fellowship
```

## Deployment Philosophy

The deployment system is designed to work cleanly:
- **Terraform manages state** - No manual imports needed
- **One script for deployment** - `setup_classroom.sh` handles everything
- **Clean workflows** - Destroy and recreate when needed, not patch
- **Idempotent** - Safe to run multiple times

## Deployment Scenarios

### Fresh Deployment (Recommended for New Environments)

Deploy everything from scratch:

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment dev
```

**Time**: ~15-20 minutes

### Update Existing Deployment

Update existing infrastructure by running the same command again. Terraform will:
- Detect existing resources
- Update what needs updating
- Create new resources if needed
- Preserve existing data (DynamoDB tables, etc.)

**Time**: ~5-10 minutes (depending on changes)

### Clean Slate (Destroy and Recreate)

If you need a completely fresh start:

```bash
# Step 1: Destroy existing infrastructure
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment dev \
  --destroy

# Step 2: Deploy fresh
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment dev
```

:::warning
This will delete all resources including EC2 instances, DynamoDB tables, Lambda functions, and CloudFront distributions.
:::

**Time**: ~20-25 minutes total

## Partial Deployments

### Deploy Only Common Infrastructure

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --only-common
```

Useful for:
- Updating shared resources (CloudFront, S3, common Lambda)
- Initial setup before workshop deployment

### Deploy Only Workshop Infrastructure

```bash
# Deploy only fellowship workshop
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop fellowship \
  --environment dev \
  --only-workshop
```

Useful for:
- Adding a new workshop
- Updating workshop-specific resources
- Testing workshop changes

### Manual Partial Deployments

For more granular control, use Terraform directly:

```bash
cd iac/aws

# Deploy only common
terraform apply -target=module.common

# Deploy only fellowship
terraform apply -target=module.workshop_fellowship

# Deploy only testus_patronus
terraform apply -target=module.workshop_testus_patronus

# Deploy everything
terraform apply
```

## Infrastructure Structure

The infrastructure is consolidated into a single root module at `iac/aws/`:

```
iac/aws/
├── main.tf              # Root module (includes common + workshops)
├── backend.tf           # Single backend configuration
├── variables.tf        # Root-level variables
├── outputs.tf          # Aggregate outputs
└── modules/
    ├── common/         # Common infrastructure module
    └── workshop/       # Parameterized workshop module
```

### Common Infrastructure (`module.common`)
- S3 bucket for React frontend
- CloudFront distribution for instance manager
- Lambda functions (instance manager, stop old instances, admin cleanup)
- IAM roles and policies for Lambda
- SSM parameters for configuration
- Secrets Manager for passwords
- Security groups and compute resources

### Workshop Infrastructure (`module.workshop_*`)
- DynamoDB table for instance assignments
- DynamoDB table for tutorial sessions
- SSM parameters for workshop timeouts
- IAM policies and roles for restricted users
- Lambda functions (user management, status, dify-jira-api)
- CloudFront distributions for workshop domains
- Resource groups for organization

## Environment Management

Each environment has separate:
- Terraform state
- DynamoDB tables
- SSM parameters
- IAM resources

### Development Environment

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment dev
```

### Staging Environment

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment staging
```

### Production Environment

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment prod
```

## Verification

After deployment, verify everything works:

1. **Check Terraform outputs**:
   ```bash
   cd iac/aws
   terraform output
   ```

2. **Access the frontend**:
   - CloudFront URL: Check Terraform outputs
   - Custom domain: If configured, use that

3. **Test Lambda functions**:
   - Instance Manager: Create an instance via UI
   - Check CloudWatch logs for errors

4. **Verify resources in AWS Console**:
   - Lambda functions exist and have correct code
   - DynamoDB tables exist
   - CloudFront distribution is deployed
   - S3 buckets have correct content

## Cleanup

To remove everything:

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment dev \
  --destroy
```

This will:
- Destroy all infrastructure
- Keep Terraform state backend (S3 bucket, DynamoDB table)
- You can redeploy later using the same state backend

To completely remove everything including state backend:

1. Destroy infrastructure (above)
2. Manually delete S3 state bucket
3. Manually delete DynamoDB lock table
