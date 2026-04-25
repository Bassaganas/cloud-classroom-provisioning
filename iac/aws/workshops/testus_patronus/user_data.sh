#!/bin/bash
# Minimal user_data.sh - Downloads and executes setup script from S3
# This avoids SSM parameter size limits (8KB) and follows AWS best practices
set -e

# Logging setup - redirect all output to log file
LOG_FILE="/var/log/user-data.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

IMDS_BASE_URL="http://169.254.169.254/latest"
IMDS_TOKEN=""

get_imds_token() {
    if [ -n "$IMDS_TOKEN" ]; then
        echo "$IMDS_TOKEN"
        return 0
    fi

    IMDS_TOKEN=$(curl -s --max-time 5 --connect-timeout 2 -X PUT "${IMDS_BASE_URL}/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || echo "")

    if [ -n "$IMDS_TOKEN" ]; then
        echo "$IMDS_TOKEN"
        return 0
    fi

    return 1
}

get_instance_metadata() {
    local path="$1"
    local token
    token=$(get_imds_token 2>/dev/null || echo "")

    if [ -n "$token" ]; then
        curl -s --max-time 5 --connect-timeout 2 -H "X-aws-ec2-metadata-token: ${token}" \
            "${IMDS_BASE_URL}/meta-data/${path}" 2>/dev/null || echo ""
    else
        curl -s --max-time 5 --connect-timeout 2 "${IMDS_BASE_URL}/meta-data/${path}" 2>/dev/null || echo ""
    fi
}

log "=========================================="
log "Starting EC2 instance user data script"
INSTANCE_ID=$(get_instance_metadata "instance-id")
log "Instance: ${INSTANCE_ID:-N/A}"
log "=========================================="

# Get AWS region with retries and fallback
AWS_REGION=""
for i in {1..5}; do
    AWS_REGION=$(get_instance_metadata "placement/region")
    [ -n "$AWS_REGION" ] && break
    [ $i -lt 5 ] && sleep 2
done
[ -z "$AWS_REGION" ] && AWS_REGION="eu-west-3" && log "Using default region: $AWS_REGION" || log "Region: $AWS_REGION"

# Get SUT bucket from SSM (contains setup script)
log "Retrieving SUT bucket from SSM: /classroom/testus_patronus/sut-bucket"
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/testus_patronus/sut-bucket" --query "Parameter.Value" --output text --region "${AWS_REGION}" 2>&1)
if [ $? -ne 0 ] || [ -z "$SUT_BUCKET" ] || [ "$SUT_BUCKET" = "None" ]; then
    log "ERROR: Failed to get SUT bucket from SSM"
    log "Error: $SUT_BUCKET"
    exit 1
fi
log "SUT bucket: $SUT_BUCKET"

# Download setup script from S3
SETUP_SCRIPT="/tmp/setup_testus_patronus.sh"
log "Downloading setup script from S3..."
if ! aws s3 cp "s3://${SUT_BUCKET}/setup_testus_patronus.sh" "$SETUP_SCRIPT" --region "${AWS_REGION}" >/dev/null 2>&1; then
    log "ERROR: Failed to download setup script from S3"
    log "Expected location: s3://${SUT_BUCKET}/setup_testus_patronus.sh"
    exit 1
fi

# Make script executable
chmod +x "$SETUP_SCRIPT"
log "✓ Setup script downloaded and made executable"

# Pass environment variables to setup script (domain information from Lambda)
# These are injected by Lambda into user_data before instance creation
if [ -n "$CADDY_DOMAIN" ]; then
    export CADDY_DOMAIN
    log "Domain from user_data: $CADDY_DOMAIN"
fi
if [ -n "$MACHINE_NAME" ]; then
    export MACHINE_NAME
    log "Machine name from user_data: $MACHINE_NAME"
fi
if [ -n "$WORKSHOP_NAME" ]; then
    export WORKSHOP_NAME
    log "Workshop name from user_data: $WORKSHOP_NAME"
fi
if [ -n "$DIFY_VERSION_STRATEGY" ]; then
    export DIFY_VERSION_STRATEGY
    log "Dify version strategy from user_data: $DIFY_VERSION_STRATEGY"
fi

# Execute setup script (preserves environment)
log "Executing setup script..."
exec "$SETUP_SCRIPT"
