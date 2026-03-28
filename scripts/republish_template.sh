#!/bin/bash

# Quick script to republish the template to SSM without running full terraform apply
# This is useful when user_data.sh is updated but infrastructure hasn't changed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default values
ENVIRONMENT="dev"
REGION="eu-west-1"
WORKSHOP_ROOT="fellowship"

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
    --workshop)
      WORKSHOP_ROOT="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [--environment <dev|staging|prod>] [--region <aws-region>] [--workshop <name>]"
      echo ""
      echo "Republishes the template config to SSM Parameter Store with updated user_data.sh"
      exit 0
      ;;
    *)
      echo "Unknown parameter: $1"
      exit 1
      ;;
  esac
done

# Check prerequisites
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not installed"
  exit 1
fi

if ! command -v terraform >/dev/null 2>&1; then
  echo "Error: terraform is required but not installed"
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: aws CLI is required but not installed"
  exit 1
fi

echo "Republishing template for workshop: $WORKSHOP_ROOT"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo ""

cd "${ROOT_DIR}/iac/aws"

# Initialize terraform if needed
terraform init -backend=false >/dev/null 2>&1 || terraform init -reconfigure >/dev/null 2>&1

# Get template configs from root module outputs
templates_json="{}"

fellowship_template=$(terraform output -json workshop_fellowship_template_config 2>/dev/null || echo "null")
if [ "$fellowship_template" != "null" ] && [ -n "$fellowship_template" ]; then
  templates_json=$(echo "$templates_json" | jq --arg name "fellowship" --argjson tmpl "$fellowship_template" '. + {($name): $tmpl}')
  echo "✓ Added template for workshop: fellowship"
fi

testus_template=$(terraform output -json workshop_testus_patronus_template_config 2>/dev/null || echo "null")
if [ "$testus_template" != "null" ] && [ -n "$testus_template" ]; then
  templates_json=$(echo "$templates_json" | jq --arg name "testus_patronus" --argjson tmpl "$testus_template" '. + {($name): $tmpl}')
  echo "✓ Added template for workshop: testus_patronus"
fi

# Check if we have any templates to publish
template_count=$(echo "$templates_json" | jq 'length')
if [ "$template_count" -eq 0 ]; then
  echo "Error: No workshop templates found"
  exit 1
fi

templates_param="/classroom/templates/${ENVIRONMENT}"

echo ""
echo "Publishing $template_count individual workshop parameter(s) and combined map to SSM..."
echo "Base path: $templates_param"

# Publish individual per-workshop parameters (preferred by Lambda over the combined map)
# This mirrors what publish_template_map() does in setup_aws.sh
workshop_names=$(echo "$templates_json" | jq -r 'keys[]')
for workshop_name in $workshop_names; do
  workshop_template=$(echo "$templates_json" | jq --arg name "$workshop_name" '.[$name]')
  individual_param="${templates_param}/${workshop_name}"
  if aws ssm put-parameter \
    --name "$individual_param" \
    --type "String" \
    --value "$workshop_template" \
    --tier "Standard" \
    --overwrite \
    --region "$REGION" >/dev/null 2>&1; then
    echo "✓ Published individual parameter: $individual_param"
  else
    echo "✗ Failed to publish individual parameter: $individual_param"
    exit 1
  fi
done

# Also publish the combined map as a fallback (Advanced tier for size)
if aws ssm put-parameter \
  --name "$templates_param" \
  --type "String" \
  --value "$templates_json" \
  --tier "Advanced" \
  --overwrite \
  --region "$REGION" >/dev/null 2>&1; then
  echo "✓ Published combined fallback map to SSM (Advanced tier)"
  echo "  Workshops in map: $(echo "$templates_json" | jq -r 'keys | join(", ")')"
  echo ""
  echo "New instances created via EC2 Manager will now use the updated user_data.sh"
else
  echo "✗ Failed to publish combined template map to SSM"
  exit 1
fi
