---
sidebar_position: 1
---

# Troubleshooting

## Common Issues

### Terraform State Locked

```bash
cd iac/aws
terraform force-unlock <LOCK_ID>
# Or use the script
./scripts/setup_classroom.sh --name my-class --cloud aws --force-unlock
```

### Lambda Packaging Fails

```bash
# Install missing dependencies
pip3 install virtualenv
./scripts/package_lambda.sh --cloud aws
```

### AWS Credentials Not Found

```bash
aws configure
# Or use environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
```

### Backend Already Exists

- The script handles existing backends gracefully
- Use `--destroy` to clean up if needed

## Deployment Issues

### Resources Already Exist

If Terraform tries to create resources that already exist:

1. **Check if resources are in Terraform state**:
   ```bash
   cd iac/aws
   terraform state list
   ```

2. **If resources exist in AWS but not in state**:
   - This shouldn't happen with clean deployments
   - Use `--destroy` then redeploy for a fresh start

3. **If resources exist in state but Terraform wants to recreate**:
   - Run `terraform refresh` to sync state
   - Then `terraform plan` to see what Terraform wants to do

### Deployment Fails Midway

If deployment fails:

1. **Check the error message** - It usually tells you what went wrong
2. **Check Terraform state**:
   ```bash
   cd iac/aws
   terraform state list
   ```
3. **Retry the deployment** - Terraform is idempotent and will continue where it left off
4. **If stuck, use Clean Slate** - Destroy and recreate

### Frontend Not Updating

If frontend changes aren't showing:

1. **Rebuild and redeploy frontend**:
   ```bash
   ./scripts/build_frontend.sh --environment dev --region eu-west-3
   ```

2. **Clear CloudFront cache** (if using custom domain):
   - Go to AWS Console → CloudFront
   - Select your distribution
   - Click "Invalidations" → "Create invalidation"
   - Enter `/*` and create

## CloudFront Issues

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

## Debug Mode

Enable verbose Terraform output:

```bash
export TF_LOG=DEBUG
./scripts/setup_classroom.sh --name debug-class --cloud aws
```
