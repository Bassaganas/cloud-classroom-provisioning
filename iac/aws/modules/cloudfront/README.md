# CloudFront Module

This module manages CloudFront distribution and ACM certificate for custom domain.

## Resources

- **ACM Certificate**: SSL/TLS certificate in us-east-1 (required for CloudFront)
- **Certificate Validation**: DNS validation for the certificate (optional - can be done manually)
- **CloudFront Distribution**: CDN distribution pointing to Lambda Function URL

## Requirements

- Certificate must be in us-east-1 region (AWS requirement)
- DNS validation records must be added to domain DNS
- Custom domain CNAME must point to CloudFront distribution

## Deployment Steps

### Step 1: Initial Deployment (Certificate Creation)

1. Run `terraform apply` - this will create the ACM certificate
2. Get the DNS validation records:
   ```bash
   terraform output acm_certificate_validation_records
   ```
3. Add the DNS validation record to GoDaddy DNS

### Step 2: Certificate Validation (Optional - Manual)

**Option A: Let Terraform wait for validation (recommended)**
- After adding DNS records, run `terraform apply` again
- Terraform will wait up to 10 minutes for validation

**Option B: Skip automatic validation**
- Comment out `aws_acm_certificate_validation.cert` resource in `main.tf`
- Comment out the `depends_on` in CloudFront distribution
- Run `terraform apply` to create CloudFront
- Validate certificate manually in AWS Console
- Uncomment the resources and run `terraform apply` again

### Step 3: Final DNS Configuration

1. Get CloudFront domain:
   ```bash
   terraform output instance_manager_cloudfront_domain
   ```
2. Add CNAME record in GoDaddy:
   - Name: `ec2-management`
   - Value: `<cloudfront-domain-from-output>`
   - TTL: 600

### Step 4: Access

Wait 5-15 minutes for DNS propagation, then access:
- `https://ec2-management.testingfantasy.com/ui`

## Outputs

- CloudFront domain name
- Custom URL
- Certificate validation records (for DNS configuration)
