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
