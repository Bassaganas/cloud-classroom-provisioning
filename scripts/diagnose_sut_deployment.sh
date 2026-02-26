#!/bin/bash

# Diagnostic script to check why SUT is not deployed on EC2 instances

set -e

INSTANCE_ID="${1:-}"
REGION="${2:-eu-west-1}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Usage: $0 <instance-id> [region]"
  echo "Example: $0 i-091e913b4a55467e9 eu-west-1"
  exit 1
fi

echo "=========================================="
echo "SUT Deployment Diagnostic"
echo "=========================================="
echo "Instance ID: $INSTANCE_ID"
echo "Region: $REGION"
echo ""

# 1. Check if SSM parameter exists
echo "1. Checking SSM Parameter /classroom/fellowship/sut-bucket..."
SUT_BUCKET_PARAM=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --region "$REGION" --query "Parameter.Value" --output text 2>/dev/null || echo "NOT_FOUND")
if [ "$SUT_BUCKET_PARAM" = "NOT_FOUND" ]; then
  echo "   ✗ SSM Parameter /classroom/fellowship/sut-bucket NOT FOUND"
  echo "   This is the root cause! The S3 bucket name is not in SSM."
  echo ""
  echo "   To fix:"
  echo "   1. Check if S3 bucket was created:"
  echo "      aws s3 ls | grep fellowship-sut"
  echo "   2. Check Terraform state for workshop_fellowship module"
  echo "   3. Re-run terraform apply if needed"
else
  echo "   ✓ SSM Parameter found: $SUT_BUCKET_PARAM"
fi
echo ""

# 2. Check if S3 bucket exists and has the file
if [ "$SUT_BUCKET_PARAM" != "NOT_FOUND" ]; then
  echo "2. Checking S3 bucket: $SUT_BUCKET_PARAM..."
  if aws s3 ls "s3://${SUT_BUCKET_PARAM}/fellowship-sut.tar.gz" --region "$REGION" >/dev/null 2>&1; then
    echo "   ✓ SUT tarball exists in S3"
    FILE_SIZE=$(aws s3 ls "s3://${SUT_BUCKET_PARAM}/fellowship-sut.tar.gz" --region "$REGION" --human-readable --summarize | grep "Total Size" | awk '{print $3, $4}')
    echo "   File size: $FILE_SIZE"
  else
    echo "   ✗ SUT tarball NOT FOUND in S3 bucket"
    echo "   To fix: Run ./scripts/setup_aws.sh to upload SUT to S3"
  fi
else
  echo "2. Skipping S3 check (SSM parameter not found)"
fi
echo ""

# 3. Check instance IAM role permissions
echo "3. Checking instance IAM role..."
INSTANCE_PROFILE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' --output text 2>/dev/null || echo "NOT_FOUND")
if [ "$INSTANCE_PROFILE" != "NOT_FOUND" ] && [ "$INSTANCE_PROFILE" != "None" ]; then
  echo "   ✓ Instance has IAM role: $INSTANCE_PROFILE"
  ROLE_NAME=$(echo "$INSTANCE_PROFILE" | awk -F'/' '{print $NF}')
  echo "   Role name: $ROLE_NAME"
  
  # Check if role has S3 permissions
  if aws iam get-role-policy --role-name "$ROLE_NAME" --policy-name "ec2-sut-s3-access-*" --region "$REGION" >/dev/null 2>&1; then
    echo "   ✓ IAM role has S3 access policy for SUT bucket"
  else
    echo "   ⚠ Could not verify S3 access policy (may need manual check)"
  fi
else
  echo "   ✗ Instance does NOT have an IAM role"
  echo "   This will prevent S3 access!"
fi
echo ""

# 4. Check user_data execution logs
echo "4. Checking user_data execution (via SSM Session Manager)..."
echo "   To check user_data logs on the instance, run:"
echo "   sudo cat /var/log/cloud-init-output.log | grep -i 'fellowship\|sut'"
echo "   sudo cat /var/log/cloud-init.log | grep -i 'fellowship\|sut'"
echo ""

# 5. Check if instance can access SSM parameter
echo "5. Testing instance access to SSM parameter..."
echo "   Connect to instance via SSM and run:"
echo "   aws ssm get-parameter --name '/classroom/fellowship/sut-bucket' --region $REGION --query 'Parameter.Value' --output text"
echo ""

# 6. Check Terraform outputs
echo "6. Checking Terraform outputs..."
cd "$(dirname "$0")/../iac/aws" 2>/dev/null || echo "   ⚠ Cannot access iac/aws directory"
if [ -f "terraform.tfstate" ] || [ -d ".terraform" ]; then
  SUT_BUCKET_OUTPUT=$(terraform output -raw sut_bucket_name 2>/dev/null || echo "NOT_FOUND")
  if [ "$SUT_BUCKET_OUTPUT" != "NOT_FOUND" ] && [ -n "$SUT_BUCKET_OUTPUT" ]; then
    echo "   ✓ Terraform output sut_bucket_name: $SUT_BUCKET_OUTPUT"
  else
    echo "   ✗ Terraform output sut_bucket_name not found or empty"
    echo "   This suggests the S3 module wasn't created"
  fi
else
  echo "   ⚠ Terraform not initialized in iac/aws"
fi
echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
if [ "$SUT_BUCKET_PARAM" = "NOT_FOUND" ]; then
  echo "ROOT CAUSE: SSM Parameter /classroom/fellowship/sut-bucket does not exist"
  echo ""
  echo "This means:"
  echo "  1. The S3 bucket may not have been created"
  echo "  2. The SSM parameter was not created"
  echo "  3. The workshop_fellowship module may not have been applied"
  echo ""
  echo "Solution:"
  echo "  1. Verify Terraform apply completed successfully"
  echo "  2. Check if module.workshop_fellowship was applied"
  echo "  3. Re-run: ./scripts/setup_classroom.sh --name fellowship-test --workshop fellowship --environment dev"
else
  echo "SSM Parameter exists. Check:"
  echo "  1. Instance IAM role has S3 permissions"
  echo "  2. user_data.sh executed successfully (check cloud-init logs)"
  echo "  3. SUT tarball exists in S3 bucket"
fi
echo ""
