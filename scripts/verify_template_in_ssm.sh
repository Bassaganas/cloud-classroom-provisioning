#!/bin/bash

# Script to verify the template in SSM has the updated user_data.sh

set -e

ENVIRONMENT="${1:-dev}"
REGION="${2:-eu-west-1}"
WORKSHOP_NAME="${3:-fellowship}"

echo "=========================================="
echo "Template Verification Script"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Workshop: $WORKSHOP_NAME"
echo ""

TEMPLATE_PARAM="/classroom/templates/${ENVIRONMENT}/${WORKSHOP_NAME}"

echo "1. Checking if template exists in SSM..."
if ! aws ssm get-parameter --name "$TEMPLATE_PARAM" --region "$REGION" >/dev/null 2>&1; then
    echo "   ✗ Template not found at: $TEMPLATE_PARAM"
    echo ""
    echo "   This means the template was not published to SSM."
    echo "   Solution: Run ./scripts/setup_classroom.sh to publish templates"
    exit 1
fi

echo "   ✓ Template found in SSM"
echo ""

echo "2. Extracting user_data from template..."
TEMPLATE_JSON=$(aws ssm get-parameter --name "$TEMPLATE_PARAM" --region "$REGION" --query "Parameter.Value" --output text)

if ! command -v jq >/dev/null 2>&1; then
    echo "   ⚠ jq not found, cannot decode template. Install jq to see full details."
    exit 0
fi

USER_DATA_B64=$(echo "$TEMPLATE_JSON" | jq -r '.user_data_base64 // empty')

if [ -z "$USER_DATA_B64" ] || [ "$USER_DATA_B64" = "null" ]; then
    echo "   ✗ Template does not contain user_data_base64"
    echo ""
    echo "   Template keys:"
    echo "$TEMPLATE_JSON" | jq -r 'keys[]' || echo "   (cannot parse JSON)"
    exit 1
fi

echo "   ✓ Template contains user_data_base64"
echo ""

echo "3. Decoding and checking user_data content..."
USER_DATA=$(echo "$USER_DATA_B64" | base64 -d 2>/dev/null || echo "")

if [ -z "$USER_DATA" ]; then
    echo "   ✗ Failed to decode user_data_base64"
    exit 1
fi

echo "   ✓ User data decoded successfully (length: ${#USER_DATA} characters)"
echo ""

echo "4. Checking for SUT deployment code in user_data..."
if echo "$USER_DATA" | grep -qi "fellowship.*sut\|fellowship-sut"; then
    echo "   ✓ User data contains 'fellowship-sut' - SUT deployment code found"
else
    echo "   ✗ User data does NOT contain 'fellowship-sut'"
    echo "   This means the template has the OLD user_data.sh without SUT deployment"
    echo ""
    echo "   Solution:"
    echo "   1. Verify iac/aws/workshops/fellowship/user_data.sh has SUT deployment code"
    echo "   2. Run: ./scripts/setup_classroom.sh to republish templates"
    exit 1
fi

echo ""

echo "5. Checking for improved error handling in user_data..."
if echo "$USER_DATA" | grep -q "LOG_FILE=\"/var/log/user-data.log\""; then
    echo "   ✓ User data has improved logging (LOG_FILE variable found)"
else
    echo "   ⚠ User data may not have improved logging"
fi

if echo "$USER_DATA" | grep -q "docker compose"; then
    echo "   ✓ User data uses 'docker compose' (correct plugin syntax)"
else
    echo "   ⚠ User data may use 'docker-compose' (old syntax)"
fi

echo ""

echo "6. Checking template metadata..."
AMI_ID=$(echo "$TEMPLATE_JSON" | jq -r '.ami_id // "not set"')
INSTANCE_TYPE=$(echo "$TEMPLATE_JSON" | jq -r '.instance_type // "not set"')
APP_PORT=$(echo "$TEMPLATE_JSON" | jq -r '.app_port // "not set"')

echo "   AMI ID: $AMI_ID"
echo "   Instance Type: $INSTANCE_TYPE"
echo "   App Port: $APP_PORT"
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo "✓ Template exists in SSM"
echo "✓ Template contains user_data_base64"
echo "✓ User data contains SUT deployment code"
echo ""
echo "The template is correctly configured!"
echo ""
echo "Note: If instances still don't get SUT deployed:"
echo "  1. Lambda function may be using cached template (wait 60s or redeploy Lambda)"
echo "  2. Check Lambda logs to see which template is being used"
echo "  3. Verify workshop_name parameter is 'fellowship' when creating instances"
echo ""
