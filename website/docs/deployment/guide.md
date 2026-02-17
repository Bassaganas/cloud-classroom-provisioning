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

## Destroying Infrastructure

```bash
# Destroy classroom infrastructure (keeps backend for reuse)
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-1 \
  --environment dev \
  --destroy
```
