# SUT Deployment Troubleshooting Guide

## Root Cause Analysis

The SUT is not being deployed on EC2 instances because:

1. **Template Cache Issue**: The Lambda function caches templates for 5 minutes (now reduced to 60 seconds). If the template was cached before `user_data.sh` was updated, instances will use the old template.

2. **Template Not Republished**: After updating `user_data.sh`, the template must be republished to SSM. The template is only republished when running `./scripts/setup_classroom.sh` or `./scripts/setup_aws.sh`.

3. **Workshop Name Mismatch**: The Lambda function looks for templates using the `workshop_name` parameter. If the frontend doesn't pass `workshop: 'fellowship'`, the Lambda may use the default `WORKSHOP_NAME` environment variable (which is 'classroom').

## Verification Steps

### Step 1: Verify Template in SSM

Run the verification script:

```bash
./scripts/verify_template_in_ssm.sh dev eu-west-1 fellowship
```

This will check:
- Template exists in SSM
- Template contains `user_data_base64`
- User data contains 'fellowship-sut' deployment code
- User data has improved error handling

### Step 2: Check Lambda Logs

Check CloudWatch logs for the Lambda function to see:
- Which template is being loaded
- Which workshop_name is being used
- If user_data contains 'fellowship-sut'

```bash
aws logs tail /aws/lambda/lambda-instance-manager-common-dev-euwest1 --follow --region eu-west-1
```

Look for:
- `"Creating instance for workshop: fellowship"`
- `"Template found for workshop fellowship"`
- `"User data script contains 'fellowship-sut'"`
- `"Template cache keys: ['fellowship', ...]"`

### Step 3: Verify Instance User Data

On the EC2 instance, check if user_data was executed:

```bash
# Connect via SSM
aws ssm start-session --target <instance-id> --region eu-west-1

# Check user data log
sudo cat /var/log/user-data.log

# Or check cloud-init logs
sudo cat /var/log/cloud-init-output.log | grep -i "fellowship\|sut"
```

## Solutions

### Solution 1: Republish Template (Required After user_data.sh Changes)

After updating `user_data.sh`, you MUST republish the template:

```bash
./scripts/setup_classroom.sh --name fellowship-test --workshop fellowship --environment dev
```

This will:
1. Read the updated `user_data.sh` from disk
2. Base64 encode it
3. Publish it to SSM at `/classroom/templates/dev/fellowship`

### Solution 2: Wait for Cache Expiry or Redeploy Lambda

The Lambda function caches templates for 60 seconds. Options:

**Option A: Wait 60 seconds** after republishing the template, then create a new instance.

**Option B: Redeploy Lambda** to force cache clear:

```bash
cd iac/aws
terraform apply -target=module.common.module.lambda.aws_lambda_function.instance_manager[0]
```

**Option C: Package and redeploy Lambda manually:**

```bash
./scripts/package_lambda.sh --cloud aws
cd iac/aws
terraform apply -target=module.common.module.lambda.aws_lambda_function.instance_manager[0]
```

### Solution 3: Verify Workshop Name is Passed

When creating instances via the EC2 Manager frontend:
- Ensure you're creating instances from a tutorial session (which includes workshop name)
- Or verify the API call includes `workshop: 'fellowship'` in the request body

Check Lambda logs to confirm:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/lambda-instance-manager-common-dev-euwest1 \
  --filter-pattern "Creating instance for workshop" \
  --region eu-west-1
```

## Complete Fix Workflow

1. **Update user_data.sh** (already done)
   - Fixed error handling
   - Added logging
   - Fixed docker-compose command

2. **Republish Template**:
   ```bash
   ./scripts/setup_classroom.sh --name fellowship-test --workshop fellowship --environment dev
   ```

3. **Verify Template in SSM**:
   ```bash
   ./scripts/verify_template_in_ssm.sh dev eu-west-1 fellowship
   ```

4. **Wait 60 seconds** (for cache to expire) OR redeploy Lambda

5. **Create New Instance** via EC2 Manager

6. **Verify Deployment**:
   ```bash
   ./scripts/test_sut_on_instance.sh <instance-id> eu-west-1
   ```

## Common Issues

### Issue: Template Not Found

**Symptom**: Lambda logs show "No template found for workshop: fellowship"

**Check**:
```bash
aws ssm get-parameter --name "/classroom/templates/dev/fellowship" --region eu-west-1
```

**Fix**: Run `./scripts/setup_classroom.sh` to publish templates

### Issue: Template Has Old user_data

**Symptom**: Template exists but doesn't contain 'fellowship-sut'

**Check**:
```bash
./scripts/verify_template_in_ssm.sh dev eu-west-1 fellowship
```

**Fix**: 
1. Verify `iac/aws/workshops/fellowship/user_data.sh` has SUT code
2. Run `./scripts/setup_classroom.sh` to republish

### Issue: Lambda Using Cached Template

**Symptom**: Template in SSM is correct, but instances still don't get SUT

**Check**: Lambda logs show "Using cached template map"

**Fix**: 
1. Wait 60 seconds (cache TTL)
2. OR redeploy Lambda function
3. OR clear cache by updating Lambda environment variable

### Issue: Wrong Workshop Name

**Symptom**: Lambda logs show "Creating instance for workshop: classroom" instead of "fellowship"

**Check**: 
- Frontend is passing `workshop: 'fellowship'` in API request
- Lambda environment variable `WORKSHOP_NAME` is not overriding

**Fix**: Ensure frontend passes workshop name when creating instances

## Debugging Commands

### Check Template in SSM
```bash
aws ssm get-parameter --name "/classroom/templates/dev/fellowship" --region eu-west-1 | jq -r '.Parameter.Value' | jq -r '.user_data_base64' | base64 -d | head -20
```

### Check Lambda Logs
```bash
aws logs tail /aws/lambda/lambda-instance-manager-common-dev-euwest1 --follow --region eu-west-1 | grep -i "template\|workshop\|user_data"
```

### Check Instance User Data Execution
```bash
# Via SSM
aws ssm send-command \
  --instance-ids <instance-id> \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo cat /var/log/user-data.log"]' \
  --region eu-west-1

# Get command output
aws ssm get-command-invocation \
  --command-id <command-id> \
  --instance-id <instance-id> \
  --region eu-west-1 \
  --query 'StandardOutputContent' \
  --output text
```

### Force Template Cache Refresh

Update Lambda environment variable to force cache clear:
```bash
aws lambda update-function-configuration \
  --function-name lambda-instance-manager-common-dev-euwest1 \
  --environment "Variables={TEMPLATE_MAP_CACHE_TTL=0}" \
  --region eu-west-1

# Then set it back to 60
aws lambda update-function-configuration \
  --function-name lambda-instance-manager-common-dev-euwest1 \
  --environment "Variables={TEMPLATE_MAP_CACHE_TTL=60}" \
  --region eu-west-1
```

## Expected Behavior

After fixes are applied:

1. **Template in SSM**: Contains updated `user_data.sh` with SUT deployment code
2. **Lambda Logs**: Show "User data script contains 'fellowship-sut'"
3. **Instance Boot**: User data script executes and logs to `/var/log/user-data.log`
4. **SUT Deployment**: SUT is downloaded from S3 and containers start
5. **Verification**: All 3 containers running, health endpoint returns 200

## Next Steps After Fix

1. Create a new instance via EC2 Manager
2. Wait 5-10 minutes for instance to boot
3. Run verification script: `./scripts/test_sut_on_instance.sh <instance-id>`
4. Check user data log: `sudo cat /var/log/user-data.log` on instance
5. Test SUT endpoints: `curl http://<instance-ip>/api/health`
