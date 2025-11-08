#!/bin/bash

# Script to force CloudFront distribution creation
# This script helps work around Terraform's count evaluation issues

set -e

echo "🔍 Checking current state..."

# Check if validation resources exist
INSTANCE_MGR_VALIDATION=$(terraform state list 2>/dev/null | grep "module.cloudfront_instance_manager.aws_acm_certificate_validation.cert\[0\]" || echo "")
USER_MGMT_VALIDATION=$(terraform state list 2>/dev/null | grep "module.cloudfront_user_management.aws_acm_certificate_validation.cert\[0\]" || echo "")

# Check if CloudFront distributions exist
INSTANCE_MGR_CF=$(terraform state list 2>/dev/null | grep "module.cloudfront_instance_manager.aws_cloudfront_distribution.distribution\[0\]" || echo "")
USER_MGMT_CF=$(terraform state list 2>/dev/null | grep "module.cloudfront_user_management.aws_cloudfront_distribution.distribution\[0\]" || echo "")

echo ""
echo "Current State:"
echo "  Instance Manager Validation: ${INSTANCE_MGR_VALIDATION:-NOT IN STATE}"
echo "  Instance Manager CloudFront: ${INSTANCE_MGR_CF:-NOT IN STATE}"
echo "  User Management Validation: ${USER_MGMT_VALIDATION:-NOT IN STATE}"
echo "  User Management CloudFront: ${USER_MGMT_CF:-NOT IN STATE}"
echo ""

# Check certificate status
echo "📋 Checking certificate status..."
INSTANCE_MGR_CERT_ARN=$(terraform state show 'module.cloudfront_instance_manager.aws_acm_certificate.cert' 2>/dev/null | grep 'arn ' | awk '{print $3}' || echo "")
USER_MGMT_CERT_ARN=$(terraform state show 'module.cloudfront_user_management.aws_acm_certificate.cert' 2>/dev/null | grep 'arn ' | awk '{print $3}' || echo "")

if [ -n "$INSTANCE_MGR_CERT_ARN" ]; then
  INSTANCE_MGR_STATUS=$(aws acm describe-certificate --certificate-arn "$INSTANCE_MGR_CERT_ARN" --region us-east-1 --query 'Certificate.Status' --output text 2>/dev/null || echo "UNKNOWN")
  echo "  Instance Manager Certificate: $INSTANCE_MGR_STATUS"
fi

if [ -n "$USER_MGMT_CERT_ARN" ]; then
  USER_MGMT_STATUS=$(aws acm describe-certificate --certificate-arn "$USER_MGMT_CERT_ARN" --region us-east-1 --query 'Certificate.Status' --output text 2>/dev/null || echo "UNKNOWN")
  echo "  User Management Certificate: $USER_MGMT_STATUS"
fi

echo ""

# Force creation of validation resources and CloudFront distributions
echo "🚀 Forcing creation of missing resources..."
echo ""

# Instance Manager
if [ -z "$INSTANCE_MGR_VALIDATION" ]; then
  echo "Creating Instance Manager certificate validation..."
  terraform apply -target='module.cloudfront_instance_manager.aws_acm_certificate_validation.cert[0]' -auto-approve
  echo "✅ Instance Manager validation created"
else
  echo "✅ Instance Manager validation already exists"
fi

if [ -z "$INSTANCE_MGR_CF" ]; then
  echo "Creating Instance Manager CloudFront distribution..."
  terraform apply -target='module.cloudfront_instance_manager.aws_cloudfront_distribution.distribution[0]' -auto-approve
  echo "✅ Instance Manager CloudFront distribution created"
else
  echo "✅ Instance Manager CloudFront distribution already exists"
fi

echo ""

# User Management (only if wait_for_certificate_validation is true)
if grep -q "wait_for_certificate_validation = true" main.tf | grep -A 5 "cloudfront_user_management"; then
  if [ -z "$USER_MGMT_VALIDATION" ]; then
    echo "Creating User Management certificate validation..."
    terraform apply -target='module.cloudfront_user_management.aws_acm_certificate_validation.cert[0]' -auto-approve
    echo "✅ User Management validation created"
  else
    echo "✅ User Management validation already exists"
  fi

  if [ -z "$USER_MGMT_CF" ]; then
    echo "Creating User Management CloudFront distribution..."
    terraform apply -target='module.cloudfront_user_management.aws_cloudfront_distribution.distribution[0]' -auto-approve
    echo "✅ User Management CloudFront distribution created"
  else
    echo "✅ User Management CloudFront distribution already exists"
  fi
else
  echo "ℹ️  User Management CloudFront is disabled (wait_for_certificate_validation = false)"
fi

echo ""
echo "🎉 Done! Run 'terraform output' to see CloudFront domain names."




