---
sidebar_position: 2
---

# Quick Start

Deploy a complete cloud classroom infrastructure with a single command.

## For Teaching/Training (with EC2 instances)

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-1 \
  --environment dev \
  --with-pool \
  --pool-size 10  # Number of machines you need, can be created later from ec2 manager
```

## For Development/Testing (Lambda only, no EC2 costs)

```bash
./scripts/setup_classroom.sh \
  --name dev-test \
  --cloud aws \
  --region eu-west-1 \
  --environment dev
```

## What Happens During Deployment

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

## Next Steps

- Read the [Deployment Guide](/docs/deployment/guide) for detailed instructions
- Learn about [Custom Domain Configuration](/docs/deployment/custom-domains)
- Explore [Usage Guides](/docs/usage/instructors) for instructors and students
