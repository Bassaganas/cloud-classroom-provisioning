#!/bin/bash

# Script to test if Lambda can access individual template parameters
# This verifies the IAM policy fix

set -e

ENVIRONMENT="${1:-dev}"
REGION="${2:-eu-west-1}"

echo "=========================================="
echo "Testing SSM Template Access"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo ""

# Get Lambda role ARN
LAMBDA_ROLE_NAME="iam-lambda-execution-role-common-${ENVIRONMENT}-$(echo $REGION | tr -d '-')"
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name "$LAMBDA_ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$LAMBDA_ROLE_ARN" ]; then
    echo "❌ Lambda role not found: $LAMBDA_ROLE_NAME"
    echo "Please check the role name matches your deployment"
    exit 1
fi

echo "✓ Found Lambda role: $LAMBDA_ROLE_NAME"
echo "  ARN: $LAMBDA_ROLE_ARN"
echo ""

# Test SSM parameter access using AWS CLI with Lambda role simulation
# We'll check the IAM policy directly
echo "Checking IAM policy for SSM permissions..."
echo ""

POLICY_NAME="iam-lambda-management-policy-common-${ENVIRONMENT}-$(echo $REGION | tr -d '-')"
POLICY_ARN=$(aws iam list-policies --query "Policies[?PolicyName=='${POLICY_NAME}'].Arn" --output text 2>/dev/null || echo "")

if [ -z "$POLICY_ARN" ]; then
    echo "⚠ Policy not found: $POLICY_NAME"
    echo "Checking attached policies..."
    ATTACHED_POLICIES=$(aws iam list-attached-role-policies --role-name "$LAMBDA_ROLE_NAME" --query 'AttachedPolicies[*].PolicyName' --output text 2>/dev/null || echo "")
    if [ -n "$ATTACHED_POLICIES" ]; then
        echo "Attached policies: $ATTACHED_POLICIES"
    fi
else
    echo "✓ Found policy: $POLICY_NAME"
    echo "  ARN: $POLICY_ARN"
    echo ""
    echo "Checking policy document for SSM permissions..."
    
    POLICY_VERSION=$(aws iam get-policy --policy-arn "$POLICY_ARN" --query 'Policy.DefaultVersionId' --output text)
    POLICY_DOC=$(aws iam get-policy-version --policy-arn "$POLICY_ARN" --version-id "$POLICY_VERSION" --query 'PolicyVersion.Document' --output json)
    
    # Check if individual template parameters are allowed
    if echo "$POLICY_DOC" | grep -q "classroom/templates/${ENVIRONMENT}/\*"; then
        echo "✓ Policy allows individual template parameters: /classroom/templates/${ENVIRONMENT}/*"
    else
        echo "❌ Policy does NOT allow individual template parameters"
        echo "   Expected: /classroom/templates/${ENVIRONMENT}/*"
    fi
    
    # Check if combined template map is allowed
    if echo "$POLICY_DOC" | grep -q "classroom/templates/${ENVIRONMENT}\""; then
        echo "✓ Policy allows combined template map: /classroom/templates/${ENVIRONMENT}"
    else
        echo "⚠ Policy does NOT allow combined template map (fallback)"
    fi
fi

echo ""
echo "=========================================="
echo "Testing SSM Parameter Access"
echo "=========================================="

# Test if parameters exist
TEMPLATES=("fellowship" "testus_patronus")
ALL_EXIST=true

for template in "${TEMPLATES[@]}"; do
    PARAM_PATH="/classroom/templates/${ENVIRONMENT}/${template}"
    echo ""
    echo "Testing: $PARAM_PATH"
    
    if aws ssm get-parameter --name "$PARAM_PATH" --region "$REGION" >/dev/null 2>&1; then
        echo "  ✓ Parameter exists"
        
        # Get parameter value size
        PARAM_VALUE=$(aws ssm get-parameter --name "$PARAM_PATH" --region "$REGION" --query 'Parameter.Value' --output text 2>/dev/null)
        PARAM_SIZE=${#PARAM_VALUE}
        echo "  ✓ Parameter size: $PARAM_SIZE characters"
        
        # Check if it contains user_data_base64
        if echo "$PARAM_VALUE" | grep -q "user_data_base64"; then
            echo "  ✓ Contains user_data_base64 field"
            
            # Check if it contains fellowship-sut (for fellowship template)
            if [ "$template" = "fellowship" ]; then
                if echo "$PARAM_VALUE" | grep -qi "fellowship-sut"; then
                    echo "  ✓ Contains fellowship-sut reference"
                else
                    echo "  ⚠ Does NOT contain fellowship-sut reference (may be old template)"
                fi
            fi
        else
            echo "  ⚠ Does NOT contain user_data_base64 field"
        fi
    else
        echo "  ❌ Parameter does NOT exist"
        ALL_EXIST=false
    fi
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="

if [ "$ALL_EXIST" = true ]; then
    echo "✓ All individual template parameters exist"
    echo ""
    echo "Next steps:"
    echo "1. Apply Terraform changes to update IAM policy:"
    echo "   cd iac/aws/modules/common"
    echo "   terraform apply"
    echo ""
    echo "2. Create a new instance via EC2 Manager UI"
    echo ""
    echo "3. Check Lambda logs for:"
    echo "   - '✓ Successfully loaded template for workshop: fellowship from /classroom/templates/dev/fellowship'"
    echo "   - 'Loaded workshop template map with X entries (from individual parameters)'"
    echo "   - Should NOT see: 'Using combined template map'"
else
    echo "❌ Some template parameters are missing"
    echo "   Run: ./scripts/setup_aws.sh to publish templates"
fi

echo ""
echo "=========================================="
