#!/bin/bash

# Comprehensive SUT testing script for EC2 instances
# Tests infrastructure, deployment, and functionality

set -e

INSTANCE_ID="${1:-}"
REGION="${2:-eu-west-1}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Usage: $0 <instance-id> [region]"
  echo "Example: $0 i-091e913b4a55467e9 eu-west-1"
  exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Results tracking
PASSED=0
FAILED=0
WARNINGS=0

# Function to print test result
test_result() {
    local status=$1
    local message=$2
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✓${NC} $message"
        ((PASSED++))
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}✗${NC} $message"
        ((FAILED++))
    else
        echo -e "${YELLOW}⚠${NC} $message"
        ((WARNINGS++))
    fi
}

echo "=========================================="
echo "Comprehensive SUT Testing"
echo "=========================================="
echo "Instance ID: $INSTANCE_ID"
echo "Region: $REGION"
echo ""

# Phase 1: Infrastructure Checks
echo "Phase 1: Infrastructure Verification"
echo "-----------------------------------"

# 1.1 Check SSM Parameter
echo -n "Checking SSM parameter... "
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --region "$REGION" --query "Parameter.Value" --output text 2>/dev/null || echo "")
if [ -n "$SUT_BUCKET" ] && [ "$SUT_BUCKET" != "None" ]; then
    test_result "PASS" "SSM parameter exists: $SUT_BUCKET"
else
    test_result "FAIL" "SSM parameter /classroom/fellowship/sut-bucket not found"
    echo "  Cannot continue without SSM parameter"
    exit 1
fi

# 1.2 Check S3 Bucket
echo -n "Checking S3 bucket... "
if aws s3 ls "s3://${SUT_BUCKET}/fellowship-sut.tar.gz" --region "$REGION" >/dev/null 2>&1; then
    FILE_SIZE=$(aws s3 ls "s3://${SUT_BUCKET}/fellowship-sut.tar.gz" --region "$REGION" --human-readable --summarize 2>/dev/null | grep "Total Size" | awk '{print $3, $4}' || echo "unknown")
    test_result "PASS" "SUT tarball exists in S3 (size: $FILE_SIZE)"
else
    test_result "FAIL" "SUT tarball not found in S3 bucket"
fi

# 1.3 Check Instance IAM Role
echo -n "Checking instance IAM role... "
INSTANCE_PROFILE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' --output text 2>/dev/null || echo "None")
if [ "$INSTANCE_PROFILE" != "None" ] && [ -n "$INSTANCE_PROFILE" ]; then
    ROLE_NAME=$(echo "$INSTANCE_PROFILE" | awk -F'/' '{print $NF}')
    test_result "PASS" "Instance has IAM role: $ROLE_NAME"
else
    test_result "FAIL" "Instance does not have an IAM role"
fi

# Phase 2: Instance Deployment Checks
echo ""
echo "Phase 2: Instance Deployment Verification"
echo "----------------------------------------"

# 2.1 Check Instance State
echo -n "Checking instance state... "
INSTANCE_STATE=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "unknown")
if [ "$INSTANCE_STATE" = "running" ]; then
    test_result "PASS" "Instance is running"
else
    test_result "FAIL" "Instance is not running (state: $INSTANCE_STATE)"
    echo "  Cannot continue testing - instance must be running"
    exit 1
fi

# 2.2 Check User Data Log (via SSM command)
echo -n "Checking user data execution... "
USER_DATA_LOG=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["sudo tail -100 /var/log/user-data.log 2>/dev/null || sudo tail -100 /var/log/cloud-init-output.log | grep -i fellowship"]' \
    --region "$REGION" \
    --query 'Command.CommandId' \
    --output text 2>/dev/null || echo "")

if [ -n "$USER_DATA_LOG" ]; then
    sleep 2
    # Wait for command to complete and get output
    COMMAND_OUTPUT=$(aws ssm get-command-invocation \
        --command-id "$USER_DATA_LOG" \
        --instance-id "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'StandardOutputContent' \
        --output text 2>/dev/null || echo "")
    
    if echo "$COMMAND_OUTPUT" | grep -qi "fellowship.*sut"; then
        test_result "PASS" "User data log contains SUT deployment messages"
    else
        test_result "WARN" "User data log check inconclusive (may need manual verification)"
    fi
else
    test_result "WARN" "Could not check user data log (SSM command failed)"
fi

# 2.3 Check SUT Directory
echo -n "Checking SUT directory... "
SUT_DIR_CHECK=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["test -d /home/ec2-user/fellowship-sut && echo EXISTS || echo NOT_FOUND"]' \
    --region "$REGION" \
    --query 'Command.CommandId' \
    --output text 2>/dev/null || echo "")

if [ -n "$SUT_DIR_CHECK" ]; then
    sleep 2
    DIR_RESULT=$(aws ssm get-command-invocation \
        --command-id "$SUT_DIR_CHECK" \
        --instance-id "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'StandardOutputContent' \
        --output text 2>/dev/null || echo "")
    
    if echo "$DIR_RESULT" | grep -q "EXISTS"; then
        test_result "PASS" "SUT directory exists at /home/ec2-user/fellowship-sut/"
    else
        test_result "FAIL" "SUT directory not found"
    fi
else
    test_result "WARN" "Could not check SUT directory (SSM command failed)"
fi

# 2.4 Check Docker Containers
echo -n "Checking Docker containers... "
CONTAINER_CHECK=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["sudo docker ps --format \"{{.Names}}\" | grep fellowship"]' \
    --region "$REGION" \
    --query 'Command.CommandId' \
    --output text 2>/dev/null || echo "")

if [ -n "$CONTAINER_CHECK" ]; then
    sleep 2
    CONTAINERS=$(aws ssm get-command-invocation \
        --command-id "$CONTAINER_CHECK" \
        --instance-id "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'StandardOutputContent' \
        --output text 2>/dev/null || echo "")
    
    BACKEND=$(echo "$CONTAINERS" | grep -c "fellowship-backend" || echo "0")
    FRONTEND=$(echo "$CONTAINERS" | grep -c "fellowship-frontend" || echo "0")
    NGINX=$(echo "$CONTAINERS" | grep -c "fellowship-nginx" || echo "0")
    
    if [ "$BACKEND" -eq 1 ] && [ "$FRONTEND" -eq 1 ] && [ "$NGINX" -eq 1 ]; then
        test_result "PASS" "All 3 SUT containers are running (backend, frontend, nginx)"
    else
        test_result "FAIL" "Not all containers running (backend: $BACKEND, frontend: $FRONTEND, nginx: $NGINX)"
    fi
else
    test_result "WARN" "Could not check containers (SSM command failed)"
fi

# Phase 3: SUT Functionality Testing
echo ""
echo "Phase 3: SUT Functionality Testing"
echo "----------------------------------"

# Get instance public IP
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text 2>/dev/null || echo "")

if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" = "None" ]; then
    test_result "FAIL" "Could not get instance public IP"
    echo "  Cannot test endpoints without public IP"
else
    echo "Instance Public IP: $PUBLIC_IP"
    echo ""
    
    # 3.1 Test Health Endpoint
    echo -n "Testing health endpoint... "
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://${PUBLIC_IP}/api/health" 2>/dev/null || echo "000")
    if [ "$HEALTH_RESPONSE" = "200" ]; then
        HEALTH_BODY=$(curl -s --max-time 10 "http://${PUBLIC_IP}/api/health" 2>/dev/null || echo "")
        if echo "$HEALTH_BODY" | grep -qi "healthy\|status"; then
            test_result "PASS" "Health endpoint returns 200 OK"
        else
            test_result "WARN" "Health endpoint returns 200 but unexpected response"
        fi
    else
        test_result "FAIL" "Health endpoint returned HTTP $HEALTH_RESPONSE"
    fi
    
    # 3.2 Test Swagger Documentation
    echo -n "Testing Swagger docs... "
    SWAGGER_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://${PUBLIC_IP}/api/swagger/" 2>/dev/null || echo "000")
    if [ "$SWAGGER_RESPONSE" = "200" ]; then
        test_result "PASS" "Swagger documentation accessible"
    else
        test_result "FAIL" "Swagger docs returned HTTP $SWAGGER_RESPONSE"
    fi
    
    # 3.3 Test Frontend
    echo -n "Testing frontend... "
    FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://${PUBLIC_IP}/" 2>/dev/null || echo "000")
    if [ "$FRONTEND_RESPONSE" = "200" ]; then
        FRONTEND_BODY=$(curl -s --max-time 10 "http://${PUBLIC_IP}/" 2>/dev/null || echo "")
        if echo "$FRONTEND_BODY" | grep -qi "react\|login\|fellowship"; then
            test_result "PASS" "Frontend is accessible and returns content"
        else
            test_result "WARN" "Frontend returns 200 but content may be incorrect"
        fi
    else
        test_result "FAIL" "Frontend returned HTTP $FRONTEND_RESPONSE"
    fi
    
    # 3.4 Test Authentication
    echo -n "Testing authentication... "
    AUTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://${PUBLIC_IP}/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "frodo_baggins", "password": "fellowship123"}' \
        --max-time 10 2>/dev/null || echo "000")
    
    if [ "$AUTH_RESPONSE" = "200" ]; then
        AUTH_BODY=$(curl -s -X POST "http://${PUBLIC_IP}/api/auth/login" \
            -H "Content-Type: application/json" \
            -d '{"username": "frodo_baggins", "password": "fellowship123"}' \
            --max-time 10 2>/dev/null || echo "")
        
        if echo "$AUTH_BODY" | grep -qi "access_token\|token"; then
            TOKEN=$(echo "$AUTH_BODY" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 || echo "")
            if [ -n "$TOKEN" ]; then
                test_result "PASS" "Authentication successful, token received"
                
                # 3.5 Test API with Authentication
                echo -n "Testing authenticated API endpoint... "
                API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
                    -H "Authorization: Bearer $TOKEN" \
                    "http://${PUBLIC_IP}/api/quests/" \
                    --max-time 10 2>/dev/null || echo "000")
                
                if [ "$API_RESPONSE" = "200" ]; then
                    test_result "PASS" "Authenticated API endpoint works"
                else
                    test_result "FAIL" "Authenticated API returned HTTP $API_RESPONSE"
                fi
            else
                test_result "WARN" "Authentication returned 200 but no token found"
            fi
        else
            test_result "WARN" "Authentication returned 200 but unexpected response"
        fi
    else
        test_result "FAIL" "Authentication returned HTTP $AUTH_RESPONSE"
    fi
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "SUT is correctly deployed and functional."
    echo "Access the application at: http://${PUBLIC_IP}/"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Recommendations:"
    echo "  1. Check user data log: sudo cat /var/log/user-data.log"
    echo "  2. Check container logs: sudo docker logs <container-name>"
    echo "  3. Verify IAM permissions for S3 and SSM access"
    echo "  4. Check security group allows HTTP traffic on port 80"
    exit 1
fi
