# Debugging SUT Deployment Issues

## Problem: SUT Not Deployed on EC2 Instances

If the SUT is not being deployed on EC2 instances, follow this debugging guide.

## Root Cause Analysis

Based on Lambda logs, the issue is typically one of these:

1. **Template Cache Issue**: Lambda cached the old template before it was updated
2. **Template Not Republished**: Template in SSM still has old user_data.sh
3. **User Data Not Executed**: user_data script didn't run on the instance
4. **S3/IAM Permissions**: Instance can't download SUT from S3

## Step-by-Step Debugging

### Step 1: Verify Template in SSM

Check what's actually stored in SSM Parameter Store:

```bash
# Get the template from SSM
aws ssm get-parameter \
  --name "/classroom/templates/dev/fellowship" \
  --region eu-west-1 \
  --query "Parameter.Value" \
  --output text | jq -r '.user_data_base64' | base64 -d > /tmp/user_data_from_ssm.sh

# Check the size
wc -c /tmp/user_data_from_ssm.sh

# Check for SUT deployment code
grep -i "fellowship-sut" /tmp/user_data_from_ssm.sh
grep -i "LOG_FILE" /tmp/user_data_from_ssm.sh
grep -i "s3://" /tmp/user_data_from_ssm.sh
```

**Expected Results:**
- File size: ~6,400 bytes (not 1,572 bytes)
- Contains "fellowship-sut"
- Contains "LOG_FILE"
- Contains "s3://" for S3 download

**If template is wrong:**
```bash
# Republish the template
./scripts/setup_classroom.sh --name <classroom-name> --workshop fellowship --environment dev
```

### Step 2: Check Lambda Cache

The Lambda caches templates for 60 seconds. If you just updated the template:

1. **Wait 60 seconds** for cache to expire, OR
2. **Create a new instance** after waiting

To verify cache status, check Lambda logs for:
```
Using cached template map (age: Xs, TTL: 60s)
```

If age < 60s, the cache is still active.

### Step 3: Verify Instance User Data

Check what user_data was actually passed to the instance:

```bash
# Get instance user_data
aws ec2 describe-instance-attribute \
  --instance-id i-024f39f03e9ed2c18 \
  --attribute userData \
  --region eu-west-1 \
  --query "UserData.Value" \
  --output text | base64 -d > /tmp/instance_user_data.sh

# Check size and content
wc -c /tmp/instance_user_data.sh
grep -i "fellowship-sut" /tmp/instance_user_data.sh
```

**If instance user_data doesn't match SSM template:**
- Lambda cache issue (wait 60s and create new instance)
- Template was updated after instance creation

### Step 4: Check Instance Logs

Connect to the instance and check if user_data ran:

```bash
# Connect via SSM Session Manager
aws ssm start-session --target i-024f39f03e9ed2c18 --region eu-west-1

# Once connected, check logs:
sudo cat /var/log/user-data.log
sudo tail -50 /var/log/cloud-init-output.log

# Check if SUT directory exists
ls -la /home/ec2-user/fellowship-sut/

# Check Docker containers
docker ps | grep fellowship
```

**Expected Logs:**
- `/var/log/user-data.log` should exist and contain SUT deployment steps
- Should see "Retrieving SUT bucket from SSM"
- Should see "Downloading SUT from S3"
- Should see "Deploying SUT via Docker Compose"

**If logs don't exist:**
- user_data script didn't run (check cloud-init logs)
- Script failed early (check for errors)

### Step 5: Check S3 and IAM Permissions

Verify the instance can access S3:

```bash
# On the instance, check IAM role
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/

# Check SSM parameter access
aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --region eu-west-1

# Check S3 access
aws s3 ls s3://s3-fellowship-sut-dev-euwest1/
aws s3 cp s3://s3-fellowship-sut-dev-euwest1/fellowship-sut.tar.gz /tmp/test.tar.gz
```

**If permissions fail:**
- Check IAM role policies
- Verify S3 bucket exists
- Check SSM parameter exists

## Quick Debugging Script

Use the automated debugging script:

```bash
./scripts/debug_sut_deployment.sh i-024f39f03e9ed2c18 eu-west-1 dev
```

This script will:
1. Check SSM template content
2. Check instance user_data
3. Connect to instance and check logs
4. Verify SUT directory and containers
5. Check SSM parameter and S3 access

## Common Issues and Solutions

### Issue 1: Template Cache Not Expired

**Symptoms:**
- Lambda logs show old template (1572 chars)
- Warning: "Fellowship SUT deployment code NOT FOUND"

**Solution:**
1. Wait 60 seconds for cache to expire
2. Create a new instance
3. OR manually clear cache by updating Lambda environment variable

### Issue 2: Template Not Updated in SSM

**Symptoms:**
- SSM template still has old user_data (Dify script)
- Template size is ~1,500 bytes instead of ~6,400 bytes

**Solution:**
```bash
# Republish template
./scripts/setup_classroom.sh --name <classroom-name> --workshop fellowship --environment dev
```

### Issue 3: User Data Script Didn't Run

**Symptoms:**
- `/var/log/user-data.log` doesn't exist
- No SUT directory on instance

**Solution:**
1. Check cloud-init logs: `sudo cat /var/log/cloud-init-output.log`
2. Check if user_data was passed: `aws ec2 describe-instance-attribute --instance-id <id> --attribute userData`
3. Check instance metadata: `curl http://169.254.169.254/latest/user-data`

### Issue 4: S3 Download Failed

**Symptoms:**
- Logs show "ERROR: Failed to download SUT from S3"
- SUT directory doesn't exist

**Solution:**
1. Verify S3 bucket exists: `aws s3 ls s3://s3-fellowship-sut-dev-euwest1/`
2. Verify file exists: `aws s3 ls s3://s3-fellowship-sut-dev-euwest1/fellowship-sut.tar.gz`
3. Check IAM role has `s3:GetObject` permission
4. Check SSM parameter exists: `aws ssm get-parameter --name "/classroom/fellowship/sut-bucket"`

### Issue 5: Docker Compose Failed

**Symptoms:**
- SUT directory exists but no containers running
- Logs show "ERROR: Docker Compose failed"

**Solution:**
1. Check Docker Compose plugin: `ls -la /home/ec2-user/.docker/cli-plugins/docker-compose`
2. Check docker-compose.yml: `cat /home/ec2-user/fellowship-sut/docker-compose.yml`
3. Check Docker logs: `cd ~/fellowship-sut && docker compose logs`

## Verification Checklist

After debugging, verify:

- [ ] SSM template has updated user_data.sh (~6,400 bytes)
- [ ] Template contains "fellowship-sut" and "LOG_FILE"
- [ ] Lambda cache expired (wait 60s) or new instance created
- [ ] Instance user_data matches SSM template
- [ ] `/var/log/user-data.log` exists on instance
- [ ] Logs show SUT deployment steps
- [ ] `/home/ec2-user/fellowship-sut/` directory exists
- [ ] `docker-compose.yml` exists in SUT directory
- [ ] Fellowship containers are running: `docker ps | grep fellowship`
- [ ] SUT is accessible: `curl http://<instance-ip>/api/health`

## Next Steps

If SUT is still not deployed after following this guide:

1. Check CloudWatch Logs for the Lambda function
2. Check EC2 instance system logs
3. Verify all IAM permissions are correct
4. Ensure S3 bucket and file exist
5. Contact support with debugging output
