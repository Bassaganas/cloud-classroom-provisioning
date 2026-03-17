#!/bin/bash

# Script to invalidate CloudFront cache for API paths
# This is useful when API Gateway changes or when debugging 403 errors

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Invalidating CloudFront cache for /api/* paths...${NC}"

# Get distribution ID from Terraform or use provided one
if [ -n "$1" ]; then
    DISTRIBUTION_ID="$1"
    echo "Using provided distribution ID: $DISTRIBUTION_ID"
else
    echo "Getting distribution ID from Terraform..."
    cd "$(dirname "$0")/../iac/aws" || exit 1
    DISTRIBUTION_ID=$(terraform output -raw instance_manager_cloudfront_distribution_id 2>/dev/null || echo "")
    
    if [ -z "$DISTRIBUTION_ID" ]; then
        echo "Could not get distribution ID from Terraform."
        echo "Usage: $0 <distribution-id>"
        echo "Or set it in Terraform outputs first."
        exit 1
    fi
fi

echo -e "${GREEN}Creating invalidation for distribution: $DISTRIBUTION_ID${NC}"

# Create invalidation for /api/* paths
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths "/api/*" \
    --query 'Invalidation.Id' \
    --output text)

echo -e "${GREEN}✓ Invalidation created: $INVALIDATION_ID${NC}"
echo ""
echo "The cache invalidation is in progress. It may take a few minutes to complete."
echo "You can check the status with:"
echo "  aws cloudfront get-invalidation --distribution-id $DISTRIBUTION_ID --id $INVALIDATION_ID"
