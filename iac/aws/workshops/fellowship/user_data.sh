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

log "=========================================="
log "Starting EC2 instance user data script"
log "Instance: $(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'N/A')"
log "=========================================="

# Get AWS region with retries and fallback
AWS_REGION=""
for i in {1..5}; do
    AWS_REGION=$(curl -s --max-time 5 --connect-timeout 2 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "")
    [ -n "$AWS_REGION" ] && break
    [ $i -lt 5 ] && sleep 2
done
[ -z "$AWS_REGION" ] && AWS_REGION="eu-west-1" && log "Using default region: $AWS_REGION" || log "Region: $AWS_REGION"

# Get SUT bucket from SSM (contains both SUT and setup script)
log "Retrieving SUT bucket from SSM: /classroom/fellowship/sut-bucket"
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --query "Parameter.Value" --output text --region "${AWS_REGION}" 2>&1)
if [ $? -ne 0 ] || [ -z "$SUT_BUCKET" ] || [ "$SUT_BUCKET" = "None" ]; then
    log "ERROR: Failed to get SUT bucket from SSM"
    log "Error: $SUT_BUCKET"
    exit 1
fi
log "SUT bucket: $SUT_BUCKET"

# Download setup script from S3
SETUP_SCRIPT="/tmp/setup_fellowship.sh"
log "Downloading setup script from S3..."
if ! aws s3 cp "s3://${SUT_BUCKET}/setup_fellowship.sh" "$SETUP_SCRIPT" --region "${AWS_REGION}" >/dev/null 2>&1; then
    log "ERROR: Failed to download setup script from S3"
    log "Expected location: s3://${SUT_BUCKET}/setup_fellowship.sh"
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

# Execute setup script (preserves environment)
log "Executing setup script..."
exec "$SETUP_SCRIPT"
