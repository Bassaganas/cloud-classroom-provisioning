# CloudFront Module

This module manages CloudFront distribution and ACM certificate for custom domain with CloudWatch logging support.

## Resources

- **ACM Certificate**: SSL/TLS certificate in us-east-1 (required for CloudFront)
- **Certificate Validation**: DNS validation for the certificate (optional - can be done manually)
- **CloudFront Distribution**: CDN distribution pointing to API Gateway, Lambda Function URL, or S3
- **CloudWatch Logging** (optional): Real-time logging of CloudFront requests to CloudWatch Logs
  - CloudWatch Log Group for storing logs
  - Kinesis Data Stream for real-time log ingestion
  - Lambda function to process logs and send to CloudWatch

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

## CloudWatch Logging

The module supports CloudWatch logging for CloudFront requests. When enabled, it creates:

1. **CloudWatch Log Group**: Stores all CloudFront access logs
2. **Kinesis Data Stream**: Receives real-time logs from CloudFront
3. **Lambda Function**: Processes Kinesis records and sends them to CloudWatch Logs

### Configuration

Enable logging by setting `enable_cloudwatch_logging = true` (default: true). You can configure:

- `cloudwatch_log_retention_days`: Number of days to retain logs (default: 30)
- `cloudfront_log_sampling_rate`: Percentage of requests to log, 0-100 (default: 100)
- `kinesis_shard_count`: Number of Kinesis shards (default: 1, affects throughput and cost)
- `kinesis_retention_hours`: Kinesis stream retention, 24-168 hours (default: 24)

### Viewing Logs

Logs are available in CloudWatch Logs under:
```
/aws/cloudfront/{environment}-{workshop_name}
```

You can query logs using CloudWatch Logs Insights with queries like:
```
fields @timestamp, c-ip, cs-method, cs-uri-stem, sc-status, time-to-first-byte
| filter cs-uri-stem like /api/
| sort @timestamp desc
| limit 100
```

### Log Fields

The following fields are captured in CloudFront real-time logs:
- Request information: timestamp, IP, method, URI, protocol
- Response information: status code, bytes, content type
- Performance: time-to-first-byte, edge location
- Security: SSL protocol, cipher, country
- Headers: user-agent, referer, cookies, forwarded-for

## Outputs

- CloudFront domain name
- Custom URL
- Certificate validation records (for DNS configuration)
- CloudWatch Log Group name and ARN (if logging enabled)
- Kinesis stream name and ARN (if logging enabled)