#!/bin/bash

# Extract Route53 records for backup before nuke operations
# Usage: ./scripts/extract_route53_records.sh [--domain <domain>] [--output <file>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
DOMAIN="testingfantasy.com"
OUTPUT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [--domain <domain>] [--output <file>]"
      echo ""
      echo "Extract Route53 records for backup before nuke operations"
      echo ""
      echo "Options:"
      echo "  --domain <domain>  Domain name (default: testingfantasy.com)"
      echo "  --output <file>    Output file path (default: route53_backup_<timestamp>.json)"
      echo "  --help            Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Set default output if not provided
if [ -z "$OUTPUT" ]; then
  OUTPUT="${ROOT_DIR}/route53_backup_$(date +%Y%m%d_%H%M%S).json"
fi

# Check prerequisites
if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: AWS CLI is required but not installed."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required but not installed."
  exit 1
fi

# Verify AWS credentials
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "ERROR: AWS credentials not configured or invalid."
  exit 1
fi

echo "Extracting Route53 records for domain: $DOMAIN"
echo ""

# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones --query "HostedZones[?Name=='${DOMAIN}.'].Id" --output text 2>/dev/null | cut -d'/' -f3)

if [ -z "$ZONE_ID" ]; then
  echo "ERROR: Hosted zone not found for domain: $DOMAIN"
  echo "Available hosted zones:"
  aws route53 list-hosted-zones --query "HostedZones[*].Name" --output text
  exit 1
fi

echo "Found hosted zone ID: $ZONE_ID"
echo "Extracting all resource record sets..."

# Extract all records
aws route53 list-resource-record-sets --hosted-zone-id "$ZONE_ID" > "$OUTPUT"

# Count records
RECORD_COUNT=$(jq '.ResourceRecordSets | length' "$OUTPUT")

echo ""
echo "✓ Route53 records extracted successfully!"
echo "  Output file: $OUTPUT"
echo "  Total records: $RECORD_COUNT"
echo ""
echo "Record types found:"
jq -r '.ResourceRecordSets[].Type' "$OUTPUT" | sort | uniq -c | sort -rn

echo ""
echo "Production records to preserve:"
echo "  - A records (root domain)"
echo "  - MX records (email)"
echo "  - NS records (nameservers)"
echo "  - SOA record (zone authority)"
echo "  - TXT records (SPF, domain verification)"
echo ""
echo "Backup complete. This file should be committed to version control for reference."
