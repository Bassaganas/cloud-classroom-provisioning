#!/bin/bash

# Script to delete the old combined template map from SSM
# This is safe to do since Lambda now prioritizes individual parameters

set -e

ENVIRONMENT="${1:-dev}"
REGION="${2:-eu-west-1}"

if [ -z "$ENVIRONMENT" ]; then
    echo "Usage: $0 [environment] [region]"
    echo "Example: $0 dev eu-west-1"
    exit 1
fi

TEMPLATE_MAP_PARAM="/classroom/templates/${ENVIRONMENT}"

echo "=========================================="
echo "Deleting Old Combined Template Map"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Parameter: $TEMPLATE_MAP_PARAM"
echo ""

# Check if parameter exists
if aws ssm get-parameter --name "$TEMPLATE_MAP_PARAM" --region "$REGION" >/dev/null 2>&1; then
    echo "✓ Found combined template map at: $TEMPLATE_MAP_PARAM"
    echo ""
    echo "Checking individual parameters..."
    
    # Check if individual parameters exist
    INDIVIDUAL_EXISTS=false
    for workshop in fellowship testus_patronus; do
        workshop_param="${TEMPLATE_MAP_PARAM}/${workshop}"
        if aws ssm get-parameter --name "$workshop_param" --region "$REGION" >/dev/null 2>&1; then
            echo "  ✓ Individual parameter exists: $workshop_param"
            INDIVIDUAL_EXISTS=true
        else
            echo "  ✗ Individual parameter not found: $workshop_param"
        fi
    done
    
    echo ""
    if [ "$INDIVIDUAL_EXISTS" = true ]; then
        echo "Individual parameters exist. It's safe to delete the combined map."
        echo "Lambda will use individual parameters instead."
        echo ""
        read -p "Delete combined template map? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            aws ssm delete-parameter \
                --name "$TEMPLATE_MAP_PARAM" \
                --region "$REGION"
            echo "✓ Deleted combined template map: $TEMPLATE_MAP_PARAM"
            echo ""
            echo "Lambda will now use individual parameters:"
            echo "  - ${TEMPLATE_MAP_PARAM}/fellowship"
            echo "  - ${TEMPLATE_MAP_PARAM}/testus_patronus"
        else
            echo "Cancelled. Combined map still exists but Lambda will prioritize individual parameters."
        fi
    else
        echo "⚠ WARNING: Individual parameters don't exist!"
        echo "Do NOT delete the combined map yet - you need to publish individual templates first."
        echo "Run: ./scripts/setup_classroom.sh to publish templates"
        exit 1
    fi
else
    echo "✗ Combined template map not found at: $TEMPLATE_MAP_PARAM"
    echo "Nothing to delete. Lambda is already using individual parameters."
fi

echo ""
echo "=========================================="
echo "Done"
echo "=========================================="
