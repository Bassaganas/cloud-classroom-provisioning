#!/bin/bash
# Testus Patronus EC2 Instance Setup Script
# This script is downloaded from S3 and executed by user_data.sh
# Contains all setup logic: Docker, Docker Compose, Dify, and Caddy
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
log "Testus Patronus Setup Script Started"
log "=========================================="

# Get AWS region with retries and fallback
AWS_REGION=""
for i in {1..5}; do
    AWS_REGION=$(get_instance_metadata "placement/region")
    [ -n "$AWS_REGION" ] && break
    [ $i -lt 5 ] && sleep 2
done
[ -z "$AWS_REGION" ] && AWS_REGION="eu-west-3" && log "Using default region: $AWS_REGION" || log "Region: $AWS_REGION"

# Function to wait for yum lock
wait_for_yum() {
    while sudo fuser /var/run/yum.pid >/dev/null 2>&1; do
        log "Waiting for yum lock to be released..."
        sleep 5
    done
}

# Wait for any existing yum processes to complete
log "Checking for yum locks..."
wait_for_yum

# Update and install dependencies
log "Installing Docker and Git..."
yum update -y
wait_for_yum
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user
log "✓ Docker installed and started"

# Install Docker Compose plugin
log "Installing Docker Compose plugin..."
mkdir -p /home/ec2-user/.docker/cli-plugins/
if curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o /home/ec2-user/.docker/cli-plugins/docker-compose; then
    chmod +x /home/ec2-user/.docker/cli-plugins/docker-compose
    chown -R ec2-user:ec2-user /home/ec2-user/.docker
    log "✓ Docker Compose plugin installed"
else
    log "ERROR: Failed to download Docker Compose plugin"
    exit 1
fi

# Helper function to run docker commands as ec2-user with proper group membership
run_as_ec2user_docker() {
    local cmd="$1"
    # Use sg (switch group) to ensure docker group is active in the subshell
    sg docker -c "su - ec2-user -c '$cmd'"
}

# Clone and configure Dify as ec2-user with specific version
log "Setting up Dify..."
su - ec2-user -c "git clone https://github.com/langgenius/dify.git ~/dify"
su - ec2-user -c "cd ~/dify && git checkout 1.13.3"  # Pin to stable version 1.9.1
su - ec2-user -c "cp ~/dify/docker/.env.example ~/dify/docker/.env"

# Configure Dify with minimal, documented configuration
cat >> /home/ec2-user/dify/docker/.env << 'EOF'

# ===== MINIMAL DIFY CONFIGURATION =====

# System language (officially documented in .env.example)
LANG=en_US.UTF-8

# Frontend configuration for nginx proxy
NEXT_PUBLIC_API_PREFIX=/console/api
NEXT_PUBLIC_PUBLIC_API_PREFIX=/v1

# ===== VERSION PINNING FOR STABILITY =====
# Pin Docker image versions to avoid compatibility issues
DIFY_API_VERSION=1.9.1
DIFY_WEB_VERSION=1.9.1
DIFY_WORKER_VERSION=1.9.1
DIFY_WORKER_BEAT_VERSION=1.9.1

# Database and Redis versions (stable versions)
POSTGRES_VERSION=15-alpine
REDIS_VERSION=6-alpine

# Weaviate version (stable)
WEAVIATE_VERSION=1.27.0

# ===== PORT CONFIGURATION FOR CADDY INTEGRATION =====
# Remap Dify's nginx to non-standard ports so that Caddy (the HTTPS terminator)
# can bind to ports 80 and 443.  Caddy listens on 80/443 externally and reverse-
# proxies all traffic to Dify's nginx on localhost:8080.
EXPOSE_NGINX_PORT=8080
EXPOSE_NGINX_SSL_PORT=8443

EOF

# Pre-pull specific Docker images to ensure version consistency
log "Pre-pulling Dify Docker images with specific versions..."
run_as_ec2user_docker "cd ~/dify/docker && docker compose pull"

# Start Dify services
log "Starting Dify services..."
run_as_ec2user_docker "cd ~/dify/docker && docker compose up -d"

# Wait for services to be ready
log "Waiting for Dify services to start..."
sleep 120

log "✓ Dify setup completed successfully"
log "Dify version: 1.9.1 (pinned for stability)"

# Install Caddy for HTTPS
log "Installing Caddy for HTTPS..."
CADDY_VERSION="2.7.6"
curl -1sLf "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_amd64.tar.gz" | tar -xz -C /usr/local/bin
chmod +x /usr/local/bin/caddy
log "✓ Caddy installed"

# Get instance domain for Caddy
# PRIORITY 1: Check if domain was passed via user_data environment variable
# This is the most reliable method - domain is known before instance creation
log "Getting instance domain for Caddy..."
if [ -n "$CADDY_DOMAIN" ] && [ "$CADDY_DOMAIN" != "" ]; then
    log "✓ Found Caddy domain from user_data environment: $CADDY_DOMAIN"
    # Domain is already set, no need to query EC2 tags
else
    # PRIORITY 2: Fallback to EC2 tags (requires instance ID from metadata service)
    log "Domain not in environment, attempting to get from EC2 tags..."
    INSTANCE_ID=""
    CADDY_DOMAIN="localhost"
    
    # Retry getting instance ID (metadata service may not be ready immediately)
    for i in {1..10}; do
        INSTANCE_ID=$(get_instance_metadata "instance-id")
        if [ -n "$INSTANCE_ID" ]; then
            log "✓ Got instance ID: $INSTANCE_ID"
            break
        fi
        if [ $i -lt 10 ]; then
            log "  Attempt $i/10: Instance ID not available yet, waiting 2s..."
            sleep 2
        fi
    done
    
    if [ -n "$INSTANCE_ID" ]; then
        # Get domain from instance tags (set by Lambda shortly after instance creation)
        # Lambda calls setup_caddy_domain() immediately after run_instances(), typically within ~10-20s.
        # The instance takes ~5min to reach this section (Docker install + Dify pull + 120s sleep),
        # so the tag should already be present. We retry generously (30×5s = 150s) just in case.
        log "Retrieving HttpsDomain tag from instance tags..."
        for i in {1..30}; do
            CADDY_DOMAIN=$(aws ec2 describe-tags --region "${AWS_REGION}" --filters "Name=resource-id,Values=${INSTANCE_ID}" "Name=key,Values=HttpsDomain" --query "Tags[0].Value" --output text 2>/dev/null || echo "")
            if [ -n "$CADDY_DOMAIN" ] && [ "$CADDY_DOMAIN" != "None" ] && [ "$CADDY_DOMAIN" != "" ]; then
                log "✓ Found Caddy domain from tags: $CADDY_DOMAIN"
                break
            fi
            if [ $i -lt 30 ]; then
                log "  Attempt $i/30: HttpsDomain tag not found yet, waiting 5s..."
                sleep 5
            fi
        done
    else
        log "WARNING: Could not get instance ID after retries"
    fi
    
    # Final check
    if [ "$CADDY_DOMAIN" = "localhost" ] || [ -z "$CADDY_DOMAIN" ] || [ "$CADDY_DOMAIN" = "None" ]; then
        log "WARNING: Caddy domain not found, Caddy will start with localhost"
        log "  The domain will be set automatically when Lambda retries, then restart Caddy: sudo systemctl restart caddy"
        CADDY_DOMAIN="localhost"
    fi
fi  # Close outer if/else block for domain source selection (PRIORITY 1: env var vs PRIORITY 2: EC2 tags)

# Create Caddy directory and fetch pre-issued wildcard certificate from Secrets Manager
mkdir -p /home/ec2-user/caddy/certs
log "Fetching pre-issued wildcard certificate from Secrets Manager..."

# Retrieve certificate from Secrets Manager (issued once by issue-wildcard-cert workflow)
# Secret format: {"cert": "<PEM fullchain>", "key": "<PEM private key>", "expires": "<date>"}
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id "/classroom/wildcard-cert/root" \
  --query SecretString \
  --output text \
  --region "${AWS_REGION}" 2>&1)

if [ $? -ne 0 ] || [ -z "$SECRET_JSON" ]; then
    log "ERROR: Failed to fetch wildcard certificate from Secrets Manager"
    log "  Expected secret: /classroom/wildcard-cert/root"
    log "  AWS Region: ${AWS_REGION}"
    log "  Error: $SECRET_JSON"
    exit 1
fi

# Extract certificate and private key from JSON
CERT_PEM=$(echo "$SECRET_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['cert'])" 2>/dev/null)
KEY_PEM=$(echo "$SECRET_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])" 2>/dev/null)

if [ -z "$CERT_PEM" ] || [ -z "$KEY_PEM" ]; then
    log "ERROR: Certificate or key missing from Secrets Manager secret"
    exit 1
fi

# Write certificate and key to files
echo "$CERT_PEM" > /home/ec2-user/caddy/certs/wildcard.crt
echo "$KEY_PEM" > /home/ec2-user/caddy/certs/wildcard.key
chmod 600 /home/ec2-user/caddy/certs/wildcard.key
chown -R ec2-user:ec2-user /home/ec2-user/caddy/certs
log "✓ Wildcard certificate fetched and written to /home/ec2-user/caddy/certs/"

# Create Caddyfile using pre-issued certificate
# NOTE: heredoc is unquoted (<< EOF) so ${CADDY_DOMAIN} is expanded by the shell
cat > /home/ec2-user/caddy/Caddyfile << EOF
# Caddyfile for Testus Patronus (Dify) — PRE-ISSUED WILDCARD CERTIFICATE
# Domain: ${CADDY_DOMAIN} (e.g., dify-{instance-id}.testingfantasy.com)
#
# Uses the shared *.testingfantasy.com wildcard certificate stored in AWS Secrets Manager
# and issued once by the issue-wildcard-cert GitHub Actions workflow.
#
# WHY A SHARED WILDCARD CERT:
#   Let's Encrypt limits issuance to 50 certificates/week per registered domain.
#   Issuing one wildcard cert covers unlimited instances for 90 days, avoiding rate limits.
#
# Certificate Details:
#   - Issued for: *.testingfantasy.com + testingfantasy.com
#   - Location: /home/ec2-user/caddy/certs/wildcard.{crt,key}
#   - Valid for: 90 days
#   - Renewal: Automatic monthly via GitHub Actions workflow

${CADDY_DOMAIN} {
    # Load the pre-issued wildcard certificate
    # The wildcard *.testingfantasy.com covers all instances and workshops
    tls /home/ec2-user/caddy/certs/wildcard.crt /home/ec2-user/caddy/certs/wildcard.key

    # Proxy all traffic to Dify (nginx remapped to localhost:8080 via docker-compose.override.yml)
    reverse_proxy localhost:8080
}
EOF
chown -R ec2-user:ec2-user /home/ec2-user/caddy
log "✓ Caddyfile created with pre-issued certificate for domain: ${CADDY_DOMAIN}"

# Create systemd service for Caddy
# CAP_NET_BIND_SERVICE allows ec2-user to bind to privileged ports (80, 443)
# without running the entire process as root.
cat > /etc/systemd/system/caddy.service << 'EOF'
[Unit]
Description=Caddy web server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/caddy
ExecStart=/usr/local/bin/caddy run --config /home/ec2-user/caddy/Caddyfile
Restart=always
RestartSec=5
# Grant permission to bind to ports 80 and 443 without root
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start Caddy
systemctl daemon-reload
systemctl enable caddy
systemctl start caddy
log "✓ Caddy service started"

# Final status
PUBLIC_IP=$(get_instance_metadata "public-ipv4")
[ -z "$PUBLIC_IP" ] && PUBLIC_IP="N/A"
log "=========================================="
log "Setup Complete"
log "=========================================="
log "Public IP: $PUBLIC_IP"
if [ -n "$CADDY_DOMAIN" ] && [ "$CADDY_DOMAIN" != "localhost" ]; then
    log "Dify HTTPS: https://${CADDY_DOMAIN}/"
    log "Dify HTTP: http://${PUBLIC_IP}/"
else
    log "Dify: http://${PUBLIC_IP}/"
    log "Note: HTTPS domain will be available after Lambda sets HttpsDomain tag"
fi
log "=========================================="
