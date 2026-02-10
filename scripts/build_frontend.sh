#!/bin/bash

# Standalone frontend build and deploy script
# This is a convenience wrapper - frontend deployment is integrated into setup_aws.sh
# Usage: ./scripts/build_frontend.sh [--environment dev] [--region eu-west-3]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
ENVIRONMENT="dev"
REGION="eu-west-3"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--environment dev] [--region eu-west-3]"
      exit 1
      ;;
  esac
done

echo "Building and deploying React frontend..."
echo "Note: Frontend deployment is normally handled by setup_aws.sh during infrastructure deployment"
echo ""

cd "$ROOT_DIR"

if [ ! -d "frontend/ec2-manager" ]; then
  echo "Error: Frontend directory not found at frontend/ec2-manager"
  exit 1
fi

# Check if node_modules exists, if not install dependencies
if [ ! -d "frontend/ec2-manager/node_modules" ]; then
  echo "Installing npm dependencies..."
  cd frontend/ec2-manager
  npm install
  cd "$ROOT_DIR"
fi

# Build the React app
echo "Building React app..."
cd frontend/ec2-manager

# Set API URL for production build
export VITE_API_URL="https://ec2-management-api.testingfantasy.com/api"
echo "Using API URL: $VITE_API_URL"

npm run build

if [ ! -d "dist" ]; then
  echo "Error: Build failed - dist directory not found"
  exit 1
fi

# Get S3 bucket name from Terraform
cd "$ROOT_DIR/iac/aws"
S3_BUCKET=$(terraform output -raw instance_manager_s3_bucket_name 2>/dev/null || echo "")

if [ -z "$S3_BUCKET" ]; then
  echo "Warning: Could not get S3 bucket name from Terraform output"
  echo "Please deploy the infrastructure first using: ./scripts/setup_classroom.sh"
  exit 1
fi

# Verify build output
BUILT_FILES=$(find dist -type f | wc -l | tr -d ' ')
if [ "$BUILT_FILES" -eq 0 ]; then
  echo "Error: Build directory is empty - no files to upload"
  exit 1
fi
echo "Build contains $BUILT_FILES file(s)"

# Check for required files
if [ ! -f "dist/index.html" ]; then
  echo "Warning: dist/index.html not found - build may be incomplete"
fi

echo "Uploading frontend to S3 bucket: $S3_BUCKET"
cd "$ROOT_DIR/frontend/ec2-manager"

# Sync static assets with cache headers (excluding HTML)
if ! aws s3 sync dist "s3://$S3_BUCKET" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "*.html" \
  --region "$REGION"; then
  echo "Error: Failed to upload static assets to S3"
  exit 1
fi

# Upload HTML files with no cache
if ! aws s3 sync dist "s3://$S3_BUCKET" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --include "*.html" \
  --region "$REGION"; then
  echo "Error: Failed to upload HTML files to S3"
  exit 1
fi

# Verify upload success
echo "Verifying upload..."
UPLOADED_FILES=$(aws s3 ls "s3://$S3_BUCKET" --recursive --region "$REGION" 2>/dev/null | wc -l | tr -d ' ')
if [ -z "$UPLOADED_FILES" ]; then
  echo "Warning: Could not verify uploaded file count"
elif [ "$UPLOADED_FILES" -lt "$BUILT_FILES" ]; then
  echo "Warning: Uploaded files ($UPLOADED_FILES) < Built files ($BUILT_FILES)"
else
  echo "✓ Verified: $UPLOADED_FILES file(s) uploaded to S3"
fi

echo "✓ Frontend uploaded to S3"

# Invalidate CloudFront cache
echo "Invalidating CloudFront cache..."
CLOUDFRONT_DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Aliases.Items[?contains(@, 'ec2-management.testingfantasy.com')]].Id" \
  --output text \
  --region "$REGION" 2>/dev/null || echo "")

if [ -n "$CLOUDFRONT_DIST_ID" ] && [ "$CLOUDFRONT_DIST_ID" != "None" ]; then
  INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DIST_ID" \
    --paths "/*" \
    --query "Invalidation.Id" \
    --output text \
    --region "$REGION" 2>/dev/null || echo "")
  
  if [ -n "$INVALIDATION_ID" ] && [ "$INVALIDATION_ID" != "None" ]; then
    echo "✓ CloudFront cache invalidation created: $INVALIDATION_ID"
  else
    echo "⚠ Could not create CloudFront invalidation"
  fi
else
  echo "⚠ CloudFront distribution not found"
fi

echo "Frontend deployment completed!"
