#!/bin/bash

# Script to debug SUT deployment issues
# Usage: ./scripts/debug_sut_deployment.sh <instance-id>

set -e

INSTANCE_ID="${1}"
REGION="${2:-eu-west-1}"
ENVIRONMENT="${3:-dev}"

if [ -z "$INSTANCE_ID" ]; then
    echo "Usage: $0 <instance-id> [region] [environment]"
    echo "Example: $0 i-024f39f03e9ed2c18 eu-west-1 dev"
    exit 1
fi

echo "=========================================="
echo "SUT Deployment Debugging Script"
echo "=========================================="
echo "Instance ID: $INSTANCE_ID"
echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# Step 1: Check what's in SSM template
echo "1. Checking SSM Template..."
echo "----------------------------------------"
TEMPLATE_PARAM="/classroom/templates/${ENVIRONMENT}/fellowship"
if aws ssm get-parameter --name "$TEMPLATE_PARAM" --region "$REGION" >/dev/null 2>&1; then
    echo "✓ Template exists in SSM: $TEMPLATE_PARAM"
    
    # Get template and decode user_data
    TEMPLATE_JSON=$(aws ssm get-parameter --name "$TEMPLATE_PARAM" --region "$REGION" --query "Parameter.Value" --output text)
    USER_DATA_B64=$(echo "$TEMPLATE_JSON" | jq -r '.user_data_base64')
    USER_DATA=$(echo "$USER_DATA_B64" | base64 -d)
    USER_DATA_SIZE=$(echo "$USER_DATA" | wc -c)
    
    echo "  Template size: $(echo "$TEMPLATE_JSON" | wc -c) bytes"
    echo "  User data size: $USER_DATA_SIZE characters"
    echo ""
    
    # Check for key markers
    echo "  Checking for key markers in user_data:"
    if echo "$USER_DATA" | grep -qi "fellowship-sut"; then
        echo "    ✓ Contains 'fellowship-sut'"
    else
        echo "    ✗ Does NOT contain 'fellowship-sut'"
    fi
    
    if echo "$USER_DATA" | grep -qi "LOG_FILE"; then
        echo "    ✓ Contains 'LOG_FILE'"
    else
        echo "    ✗ Does NOT contain 'LOG_FILE'"
    fi
    
    if echo "$USER_DATA" | grep -qi "s3://"; then
        echo "    ✓ Contains S3 download code"
    else
        echo "    ✗ Does NOT contain S3 download code"
    fi
    
    if echo "$USER_DATA" | grep -qi "docker compose"; then
        echo "    ✓ Contains 'docker compose'"
    else
        echo "    ✗ Does NOT contain 'docker compose'"
    fi
    
    echo ""
    echo "  First 10 lines of user_data:"
    echo "$USER_DATA" | head -10 | sed 's/^/    /'
    echo ""
else
    echo "✗ Template NOT found in SSM: $TEMPLATE_PARAM"
    exit 1
fi

# Step 2: Check instance user_data (what was actually passed)
echo "2. Checking Instance User Data..."
echo "----------------------------------------"
INSTANCE_USER_DATA=$(aws ec2 describe-instance-attribute \
    --instance-id "$INSTANCE_ID" \
    --attribute userData \
    --region "$REGION" \
    --query "UserData.Value" \
    --output text 2>/dev/null || echo "")

if [ -n "$INSTANCE_USER_DATA" ]; then
    DECODED_USER_DATA=$(echo "$INSTANCE_USER_DATA" | base64 -d)
    DECODED_SIZE=$(echo "$DECODED_USER_DATA" | wc -c)
    
    echo "✓ Instance has user_data"
    echo "  User data size: $DECODED_SIZE characters"
    echo ""
    
    # Check for key markers
    echo "  Checking for key markers in instance user_data:"
    if echo "$DECODED_USER_DATA" | grep -qi "fellowship-sut"; then
        echo "    ✓ Contains 'fellowship-sut'"
    else
        echo "    ✗ Does NOT contain 'fellowship-sut'"
    fi
    
    if echo "$DECODED_USER_DATA" | grep -qi "LOG_FILE"; then
        echo "    ✓ Contains 'LOG_FILE'"
    else
        echo "    ✗ Does NOT contain 'LOG_FILE'"
    fi
    
    echo ""
    echo "  First 10 lines of instance user_data:"
    echo "$DECODED_USER_DATA" | head -10 | sed 's/^/    /'
    echo ""
else
    echo "✗ Instance does NOT have user_data attribute"
    echo "  This means user_data was not passed during instance creation"
fi

# Step 3: Check if user_data script ran on instance
echo "3. Checking Instance User Data Execution..."
echo "----------------------------------------"
echo "Connecting to instance via SSM Session Manager..."
echo ""

# Create a temporary script to run on the instance
SSM_COMMANDS=$(cat <<'EOF'
echo "=== Checking User Data Execution ==="
echo ""

# Check if log file exists
if [ -f "/var/log/user-data.log" ]; then
    echo "✓ /var/log/user-data.log exists"
    echo "  File size: $(wc -c < /var/log/user-data.log) bytes"
    echo "  Last 20 lines:"
    tail -20 /var/log/user-data.log | sed 's/^/    /'
else
    echo "✗ /var/log/user-data.log does NOT exist"
    echo "  This means user_data script may not have run"
fi

echo ""
echo "=== Checking Cloud Init Logs ==="
if [ -f "/var/log/cloud-init-output.log" ]; then
    echo "✓ /var/log/cloud-init-output.log exists"
    if grep -qi "fellowship-sut" /var/log/cloud-init-output.log; then
        echo "  ✓ Contains 'fellowship-sut'"
    else
        echo "  ✗ Does NOT contain 'fellowship-sut'"
    fi
    echo "  Last 10 lines:"
    tail -10 /var/log/cloud-init-output.log | sed 's/^/    /'
else
    echo "✗ /var/log/cloud-init-output.log does NOT exist"
fi

echo ""
echo "=== Checking SUT Directory ==="
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    echo "✓ /home/ec2-user/fellowship-sut exists"
    echo "  Contents:"
    ls -la /home/ec2-user/fellowship-sut/ | head -10 | sed 's/^/    /'
else
    echo "✗ /home/ec2-user/fellowship-sut does NOT exist"
fi

echo ""
echo "=== Checking Docker Containers ==="
if docker ps | grep -q fellowship; then
    echo "✓ Fellowship containers are running:"
    docker ps | grep fellowship | sed 's/^/    /'
else
    echo "✗ No Fellowship containers running"
    echo "  All containers:"
    docker ps | sed 's/^/    /'
fi

echo ""
echo "=== Checking SSM Parameter ==="
AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
if aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --region "$AWS_REGION" >/dev/null 2>&1; then
    SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --query "Parameter.Value" --output text --region "$AWS_REGION")
    echo "✓ SSM parameter exists: $SUT_BUCKET"
else
    echo "✗ SSM parameter /classroom/fellowship/sut-bucket does NOT exist"
fi
EOF
)

echo "Running diagnostic commands on instance..."
aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[$(echo "$SSM_COMMANDS" | jq -Rs .)]" \
    --region "$REGION" \
    --output text \
    --query "Command.CommandId" > /tmp/ssm_command_id.txt

COMMAND_ID=$(cat /tmp/ssm_command_id.txt)
echo "Command ID: $COMMAND_ID"
echo "Waiting for command to complete..."
sleep 5

aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query "[StandardOutputContent, StandardErrorContent]" \
    --output text

echo ""
echo "=========================================="
echo "Debug Summary"
echo "=========================================="
echo "1. Check if SSM template has the updated user_data.sh"
echo "2. Check if instance received the correct user_data"
echo "3. Check if user_data script executed on the instance"
echo "4. Check if SUT directory and containers exist"
echo ""
echo "If the template in SSM doesn't have 'fellowship-sut', run:"
echo "  ./scripts/setup_classroom.sh --name <classroom-name> --workshop fellowship --environment $ENVIRONMENT"
echo ""
echo "If the instance user_data doesn't match SSM template, the Lambda cache may need to expire (60s TTL)"
echo "  Or clear the cache by waiting 60 seconds and creating a new instance"
