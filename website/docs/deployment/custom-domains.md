---
sidebar_position: 2
---

# Custom Domain Configuration

## Understanding Custom Domain Requirements

### What Requires Custom Domains?

1. **EC2 Manager (Instructor Interface)** - Recommended:
   - Frontend: `ec2-management-{environment}.testingfantasy.com`
   - API: `ec2-management-api-{environment}.testingfantasy.com`
   - **Status**: Custom domain is recommended for better UX, but infrastructure can deploy without it
   - **Without custom domain**: Access via CloudFront distribution URLs (less user-friendly)

2. **Workshop Lambda Functions (Student Access)** - Optional:
   - Testus Patronus: `testus-patronus.testingfantasy.com`
   - Fellowship: `fellowship-of-the-build.testingfantasy.com`
   - Dify Jira API: `dify-jira.testingfantasy.com`, `dify-jira-fellowship.testingfantasy.com`
   - **Status**: Fully functional without custom domains (uses Lambda Function URLs)

## Access URLs: With vs. Without Custom Domains

### EC2 Manager (Instructor Interface)

| Component | With Custom Domain | Without Custom Domain |
|-----------|-------------------|----------------------|
| Frontend | `https://ec2-management-dev.testingfantasy.com` | `https://d1234567890abc.cloudfront.net` |
| API | `https://ec2-management-api-dev.testingfantasy.com/api` | `https://abc123xyz.execute-api.eu-west-1.amazonaws.com/dev/api` |

### Workshop Lambda Functions (Student Access)

| Component | With Custom Domain | Without Custom Domain |
|-----------|-------------------|----------------------|
| Testus Patronus | `https://testus-patronus.testingfantasy.com` | `https://abc123xyz.lambda-url.eu-west-1.on.aws` |
| Fellowship | `https://fellowship-of-the-build.testingfantasy.com` | `https://def456uvw.lambda-url.eu-west-1.on.aws` |

:::note
Lambda Function URLs are always available regardless of custom domain configuration.
:::

## Deployment Scenarios

### Scenario 1: Deploy Without Custom Domains (Quick Start)

```bash
# Deploy infrastructure without DNS setup
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-1 \
  --environment dev

# Access EC2 Manager via CloudFront URL (get from Terraform outputs)
cd iac/aws
terraform output instance_manager_cloudfront_domain
# Use: https://<cloudfront-domain-from-output>

# Access Workshop Lambda via Function URL (get from Terraform outputs)
terraform output testus_patronus_lambda_function_url
# Use: <function-url-from-output>
```

### Scenario 2: Deploy With Custom Domains (Production)

```bash
# Step 1: Deploy infrastructure (creates ACM certificates)
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-1 \
  --environment dev

# Step 2: Configure DNS (see "Post-Deployment: Setting Up Custom Domain" below)
# Step 3: Complete certificate validation
cd iac/aws
terraform apply  # Completes custom domain setup
```

## Post-Deployment: Setting Up Custom Domain

:::info Optional
This section is only needed if you want to use custom domains. The infrastructure works without custom domains, but URLs will be less user-friendly.
:::

After initial deployment, configure DNS for custom domains:

1. **Get ACM Certificate Validation Records:**
   ```bash
   cd iac/aws
   terraform output instance_manager_acm_certificate_validation_records
   ```

2. **Add DNS Validation Record:**
   - Add the CNAME record to your DNS provider (Route53/GoDaddy)
   - Wait for certificate validation (5-40 minutes)

3. **Complete Deployment:**
   ```bash
   cd iac/aws
   terraform apply  # Completes certificate validation
   ```

4. **Get CloudFront Domain:**
   ```bash
   terraform output instance_manager_cloudfront_domain
   ```

5. **Add Final CNAME Record:**
   - Name: `ec2-management-{environment}`
   - Value: `<cloudfront-domain-from-step-4>`

6. **Access Your Instance Manager:**
   - URL: `https://ec2-management-{environment}.testingfantasy.com`
   - Wait 5-15 minutes for DNS propagation

## Detailed CloudFront Deployment Steps

For detailed step-by-step CloudFront deployment with GoDaddy DNS:

### Step 1: Initial Deployment

Run the setup script to create the infrastructure:

```bash
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --region eu-west-3 \
  --workshop testus_patronus \
  --environment dev
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

**IMPORTANT**: Due to a Terraform quirk with conditional resource creation, you may need to manually target the resources:

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

## Alternative: Access Without Custom Domain

If you skip DNS setup, you can still access the EC2 Manager:

```bash
cd iac/aws
# Get CloudFront distribution URL
terraform output instance_manager_cloudfront_domain
# Access at: https://<cloudfront-domain-from-output>

# Get API Gateway endpoint
terraform output instance_manager_api_gateway_url
# Access at: <api-gateway-url-from-output>/api
```

### Workshop Lambda Functions Without Custom Domains

```bash
cd iac/aws
# Get Lambda Function URLs
terraform output testus_patronus_lambda_function_url
terraform output fellowship_lambda_function_url
# Access directly at the Function URLs (no DNS setup needed)
```
