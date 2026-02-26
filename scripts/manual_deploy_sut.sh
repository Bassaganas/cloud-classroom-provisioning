#!/bin/bash

# Script to manually deploy SUT on an existing EC2 instance via SSM

set -e

INSTANCE_ID="${1:-}"
REGION="${2:-eu-west-1}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Usage: $0 <instance-id> [region]"
  echo "Example: $0 i-091e913b4a55467e9 eu-west-1"
  exit 1
fi

echo "=========================================="
echo "Manual SUT Deployment Script"
echo "=========================================="
echo "Instance ID: $INSTANCE_ID"
echo "Region: $REGION"
echo ""

# Get SSM parameter
echo "1. Getting SUT bucket from SSM..."
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --region "$REGION" --query "Parameter.Value" --output text 2>/dev/null || echo "")
if [ -z "$SUT_BUCKET" ]; then
  echo "   ✗ SSM parameter /classroom/fellowship/sut-bucket not found"
  echo "   Run terraform apply first to create the infrastructure"
  exit 1
fi
echo "   ✓ SUT bucket: $SUT_BUCKET"
echo ""

# Check if SUT exists in S3
echo "2. Verifying SUT exists in S3..."
if ! aws s3 ls "s3://${SUT_BUCKET}/fellowship-sut.tar.gz" --region "$REGION" >/dev/null 2>&1; then
  echo "   ✗ SUT tarball not found in S3"
  echo "   Run ./scripts/setup_aws.sh to upload SUT to S3"
  exit 1
fi
echo "   ✓ SUT tarball exists in S3"
echo ""

# Create deployment script
DEPLOY_SCRIPT=$(cat <<'DEPLOY_EOF'
#!/bin/bash
set -e

echo "=========================================="
echo "Deploying Fellowship SUT"
echo "=========================================="

# Get region
AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
echo "Region: $AWS_REGION"

# Get SUT bucket from SSM
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --query "Parameter.Value" --output text --region ${AWS_REGION} 2>/dev/null || echo "")

if [ -z "$SUT_BUCKET" ]; then
  echo "✗ SSM parameter /classroom/fellowship/sut-bucket not found"
  exit 1
fi

echo "SUT Bucket: $SUT_BUCKET"

# Create directory
mkdir -p /home/ec2-user/fellowship-sut
echo "Created directory: /home/ec2-user/fellowship-sut"

# Download from S3
echo "Downloading SUT from S3..."
if ! aws s3 cp "s3://${SUT_BUCKET}/fellowship-sut.tar.gz" /tmp/fellowship-sut.tar.gz --region ${AWS_REGION} 2>/dev/null; then
  echo "✗ Failed to download SUT from S3"
  exit 1
fi

# Extract
echo "Extracting SUT..."
tar -xzf /tmp/fellowship-sut.tar.gz -C /home/ec2-user/
rm -f /tmp/fellowship-sut.tar.gz

# Fix permissions
chown -R ec2-user:ec2-user /home/ec2-user/fellowship-sut
echo "Fixed permissions"

# Deploy via Docker Compose
echo "Deploying SUT via Docker Compose..."
su - ec2-user -c "cd ~/fellowship-sut && docker-compose up -d"

# Wait for services
echo "Waiting for services to start..."
sleep 30

# Check status
echo ""
echo "=========================================="
echo "Deployment Status"
echo "=========================================="
echo "Docker containers:"
docker ps --filter "name=fellowship" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "SUT Directory:"
ls -la /home/ec2-user/fellowship-sut/ | head -10

echo ""
echo "=========================================="
echo "SUT Deployment Complete"
echo "=========================================="
DEPLOY_EOF
)

# Send command via SSM
echo "3. Sending deployment command to instance via SSM..."
echo "   This will:"
echo "   - Download SUT from S3"
echo "   - Extract to /home/ec2-user/fellowship-sut"
echo "   - Deploy via Docker Compose"
echo ""

# Use SSM send-command to run the script
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[$(echo "$DEPLOY_SCRIPT" | jq -Rs .)]" \
  --region "$REGION" \
  --output-s3-bucket-name "$SUT_BUCKET" \
  --output-s3-key-prefix "ssm-commands" \
  --query "Command.CommandId" \
  --output text 2>/dev/null || echo "")

if [ -z "$COMMAND_ID" ]; then
  echo "   ⚠ Could not send SSM command (may need to use Session Manager instead)"
  echo ""
  echo "   Manual steps:"
  echo "   1. Connect to instance via SSM Session Manager"
  echo "   2. Run the following commands:"
  echo ""
  echo "$DEPLOY_SCRIPT" | sed 's/^/      /'
  exit 1
fi

echo "   ✓ Command sent. Command ID: $COMMAND_ID"
echo ""
echo "4. Waiting for command execution..."
sleep 5

# Wait for command to complete
MAX_WAIT=300
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
  STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query "Status" \
    --output text 2>/dev/null || echo "Unknown")
  
  if [ "$STATUS" = "Success" ]; then
    echo "   ✓ Command completed successfully"
    echo ""
    echo "5. Getting command output..."
    aws ssm get-command-invocation \
      --command-id "$COMMAND_ID" \
      --instance-id "$INSTANCE_ID" \
      --region "$REGION" \
      --query "StandardOutputContent" \
      --output text
    echo ""
    echo "=========================================="
    echo "SUT Deployment Complete!"
    echo "=========================================="
    exit 0
  elif [ "$STATUS" = "Failed" ] || [ "$STATUS" = "Cancelled" ] || [ "$STATUS" = "TimedOut" ]; then
    echo "   ✗ Command failed with status: $STATUS"
    echo ""
    echo "Error output:"
    aws ssm get-command-invocation \
      --command-id "$COMMAND_ID" \
      --instance-id "$INSTANCE_ID" \
      --region "$REGION" \
      --query "StandardErrorContent" \
      --output text
    exit 1
  fi
  
  echo "   Status: $STATUS (waiting...)"
  sleep 10
  WAIT_TIME=$((WAIT_TIME + 10))
done

echo "   ⚠ Command timed out after $MAX_WAIT seconds"
echo "   Check status manually:"
echo "   aws ssm get-command-invocation --command-id $COMMAND_ID --instance-id $INSTANCE_ID --region $REGION"
exit 1
