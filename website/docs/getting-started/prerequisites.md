---
sidebar_position: 1
---

# Prerequisites

Before deploying the Cloud Classroom Provisioning system, ensure you have the following prerequisites installed and configured.

## Install Required Tools

### macOS

```bash
brew install terraform awscli python3
```

### Linux

```bash
sudo apt-get update
sudo apt-get install terraform awscli python3 python3-pip
```

## Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region

# Verify access
aws sts get-caller-identity
```

## Verify Terraform

```bash
terraform version  # Should be >= 1.0.0
```

## Custom Domain Requirements

:::info Optional but Recommended

Custom domains are **optional** but recommended for better user experience.

:::

### EC2 Manager (Instructor Interface)

- **With custom domain**: `https://ec2-management-dev.testingfantasy.com`
- **Without custom domain**: Access via CloudFront distribution URL (e.g., `https://d1234567890abc.cloudfront.net`)
- The infrastructure will create ACM certificates automatically, but DNS validation records must be added post-deployment

### Workshop Lambda Functions (Student Access)

- **With custom domain**: `https://testus-patronus.testingfantasy.com`
- **Without custom domain**: Access via Lambda Function URL (e.g., `https://abc123xyz.lambda-url.eu-west-1.on.aws`)
- Workshop functions work fully without custom domains

### Route53 Hosted Zone

Required if you want to use custom domains:

- You need a Route53 hosted zone for your domain (e.g., `testingfantasy.com`)
- Or configure DNS manually with your DNS provider

See the [Custom Domain Configuration](/docs/deployment/custom-domains) section for detailed setup instructions.
