# CloudFront Custom Domain Deployment Guide

This guide explains how to deploy CloudFront distributions with custom domains for the classroom provisioning system.

## Overview

The infrastructure supports three CloudFront distributions:
1. **Instance Manager**: `ec2-management.testingfantasy.com` → Instance Manager Lambda UI
2. **User Management**: `testus-patronus.testingfantasy.com` → User Management Lambda
3. **Dify Jira API**: `dify-jira.testingfantasy.com` → Dify Jira API Lambda

## Prerequisites

- Domain `testingfantasy.com` managed in GoDaddy
- AWS credentials configured with appropriate permissions
- Terraform backend configured (via `setup_aws.sh`)

## Deployment Process

### Step 1: Initial Deployment

Run the setup script to create the infrastructure:

```bash
./scripts/setup_aws.sh testus-patronus eu-west-3 create
```

This will:
- Create ACM certificates in `us-east-1` (required for CloudFront)
- Create all Lambda functions and other infrastructure
- **NOT** create CloudFront distributions yet (certificates need validation first)

### Step 2: Get DNS Validation Records

After the initial deployment, get the DNS validation records:

```bash
cd iac/aws
terraform output instance_manager_acm_certificate_validation_records
terraform output user_management_acm_certificate_validation_records
terraform output dify_jira_acm_certificate_validation_records
```

You'll see output like:
```
toset([
  {
    "domain_name" = "ec2-management.testingfantasy.com"
    "resource_record_name" = "_abc123.ec2-management.testingfantasy.com."
    "resource_record_type" = "CNAME"
    "resource_record_value" = "_xyz789.jkddzztszm.acm-validations.aws."
  },
])
```

### Step 3: Add DNS Validation Records to GoDaddy

1. Log in to GoDaddy DNS Management for `testingfantasy.com`
2. Add CNAME records for each domain:
   - **Name**: `_abc123.ec2-management` (from `resource_record_name`, remove the trailing dot and domain)
   - **Type**: `CNAME`
   - **Value**: `_xyz789.jkddzztszm.acm-validations.aws.` (from `resource_record_value`)
   - **TTL**: `600` (or default)

   Repeat for `testus-patronus.testingfantasy.com` and `dify-jira.testingfantasy.com` if deploying those services.

3. **Wait 5-10 minutes** for DNS propagation and certificate validation

### Step 4: Verify Certificate Validation

Check certificate status:

```bash
# For Instance Manager
aws acm describe-certificate \
  --certificate-arn $(terraform output -raw instance_manager_acm_certificate_validation_records 2>/dev/null | jq -r '.[0].certificate_arn' 2>/dev/null || \
  aws acm list-certificates --region us-east-1 --query 'CertificateSummaryList[?contains(DomainName, `ec2-management.testingfantasy.com`)].CertificateArn' --output text) \
  --region us-east-1 \
  --query 'Certificate.Status' \
  --output text

# Should return: ISSUED
```

### Step 5: Enable CloudFront Distribution Creation

Edit `iac/aws/main.tf` and set `wait_for_certificate_validation = true` for the modules you want:

```hcl
module "cloudfront_instance_manager" {
  # ... other config ...
  wait_for_certificate_validation = true  # Change from false to true
}

module "cloudfront_user_management" {
  # ... other config ...
  wait_for_certificate_validation = true  # Change from false to true
}
```

### Step 6: Create CloudFront Distributions

**IMPORTANT**: Due to a Terraform quirk with conditional resource creation, you may need to use the helper script:

```bash
cd iac/aws
./deploy_cloudfront.sh
```

Or manually target the resources:

```bash
cd iac/aws
terraform apply \
  -target='module.cloudfront_instance_manager.aws_acm_certificate_validation.cert["create"]' \
  -target='module.cloudfront_instance_manager.aws_cloudfront_distribution.distribution["create"]' \
  -auto-approve
```

This will:
- Create `aws_acm_certificate_validation` resources (will complete immediately if certificates are already validated)
- Create CloudFront distributions
- Take 10-15 minutes to complete (CloudFront distribution creation is slow)

**Note**: If Terraform says "No changes", the resources may already exist or there's a state issue. Check with:
```bash
terraform state list | grep cloudfront
```

### Step 7: Get CloudFront Domain Names

After CloudFront distributions are created:

```bash
terraform output instance_manager_cloudfront_domain
terraform output user_management_cloudfront_domain
```

You'll get output like:
```
d3lgkejqbzrt1p.cloudfront.net
```

### Step 8: Add Final DNS CNAME Records to GoDaddy

Add CNAME records pointing your custom domains to CloudFront:

1. **For Instance Manager**:
   - **Name**: `ec2-management`
   - **Type**: `CNAME`
   - **Value**: `<cloudfront-domain-from-step-7>` (e.g., `d3lgkejqbzrt1p.cloudfront.net`)
   - **TTL**: `600`

2. **For User Management**:
   - **Name**: `testus-patronus`
   - **Type**: `CNAME`
   - **Value**: `<cloudfront-domain-from-step-7>`
   - **TTL**: `600`

3. **For Dify Jira API**:
   - **Name**: `dify-jira`
   - **Type**: `CNAME`
   - **Value**: `<cloudfront-domain-from-step-7>`
   - **TTL**: `600`

### Step 9: Wait for DNS Propagation

Wait 5-15 minutes for DNS propagation, then access:
- Instance Manager: `https://ec2-management.testingfantasy.com/ui`
- User Management: `https://testus-patronus.testingfantasy.com`
- Dify Jira API: `https://dify-jira.testingfantasy.com`

## Troubleshooting

### Certificate Validation Fails

- Verify DNS records are correctly added in GoDaddy
- Check for typos in the CNAME record values
- Wait longer (DNS can take up to 48 hours, but usually 5-10 minutes)
- Verify the certificate status in AWS Console (ACM in us-east-1)

### CloudFront Distribution Not Created

- Verify `wait_for_certificate_validation = true` in `main.tf`
- Check that certificate status is `ISSUED` (not `PENDING_VALIDATION`)
- Run `terraform plan` to see what Terraform wants to create
- Check for errors in `terraform apply` output

### DNS Not Resolving

- Verify CNAME records are added correctly in GoDaddy
- Check DNS propagation: `dig ec2-management.testingfantasy.com`
- Wait longer for DNS propagation (can take up to 48 hours)
- Verify CloudFront distribution is `Deployed` (not `In Progress`)

### 403 AccessDeniedException from CloudFront

- This is usually a CloudFront configuration issue
- Verify the origin (Lambda Function URL) is correct
- Check CloudFront logs in CloudWatch
- Verify the Lambda function URL is publicly accessible

### CNAMEAlreadyExists Error

This happens when:
- An old CloudFront distribution was deleted, but its CNAME record still exists in GoDaddy
- Another CloudFront distribution already uses the same domain

**Solution**:
1. Remove the old CNAME record from GoDaddy
2. Set `wait_for_certificate_validation = false` temporarily
3. Run `terraform apply` to create the new distribution
4. Add the new CNAME record pointing to the new CloudFront domain

## Automated Deployment

The `setup_aws.sh` script provides automated deployment with clear status messages:

```bash
./scripts/setup_aws.sh testus-patronus eu-west-3 create
```

The script will:
1. Show certificate validation records
2. Display CloudFront distribution status
3. Provide step-by-step instructions based on current state
4. Show what needs to be done next

## Manual Steps Required

The following steps **cannot** be automated and must be done manually:

1. ✅ Adding DNS validation records to GoDaddy (Step 3)
2. ✅ Setting `wait_for_certificate_validation = true` in `main.tf` (Step 5)
3. ✅ Adding final CNAME records to GoDaddy (Step 8)

All other steps can be automated via Terraform and the setup script.

## Reproducibility

To make this process reproducible:

1. **Initial Setup**: Run `setup_aws.sh` once to create infrastructure
2. **DNS Configuration**: Manually add DNS records (one-time per domain)
3. **Enable CloudFront**: Set `wait_for_certificate_validation = true` in `main.tf`
4. **Deploy**: Run `terraform apply` to create CloudFront distributions
5. **Final DNS**: Manually add CNAME records pointing to CloudFront

The Terraform state tracks all resources, so subsequent runs will be idempotent.

