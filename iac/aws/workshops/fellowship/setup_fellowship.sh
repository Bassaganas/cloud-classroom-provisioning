#!/bin/bash
# Fellowship EC2 Instance Setup Script
# This script is downloaded from S3 and executed by user_data.sh
# Contains all setup logic: Docker, Docker Compose, DevOps Escape Room, and Fellowship SUT
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
log "Fellowship Setup Script Started"
log "=========================================="

# Get AWS region with retries and fallback
AWS_REGION=""
for i in {1..5}; do
    AWS_REGION=$(get_instance_metadata "placement/region")
    [ -n "$AWS_REGION" ] && break
    [ $i -lt 5 ] && sleep 2
done
[ -z "$AWS_REGION" ] && AWS_REGION="eu-west-1" && log "Using default region: $AWS_REGION" || log "Region: $AWS_REGION"

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
    # This is more reliable than su - which may not pick up new group membership immediately
    sg docker -c "su - ec2-user -c '$cmd'"
}

# DevOps Escape Room stack (Jenkins + MailHog)
log "Setting up DevOps Escape Room stack..."
mkdir -p /home/ec2-user/devops-escape-room
cat > /home/ec2-user/devops-escape-room/docker-compose.yml << 'EOF'
services:
  jenkins:
    image: jenkins/jenkins:lts
    ports:
      - "8080:8080"
      - "50000:50000"
    volumes:
      - jenkins_home:/var/jenkins_home
  mailhog:
    image: mailhog/mailhog:v1.0.1
    ports:
      - "1025:1025"
      - "8025:8025"
volumes:
  jenkins_home:
EOF
chown -R ec2-user:ec2-user /home/ec2-user/devops-escape-room
if run_as_ec2user_docker "cd ~/devops-escape-room && docker compose up -d" >/dev/null 2>&1; then
    log "✓ DevOps Escape Room started"
else
    log "WARNING: Failed to start DevOps Escape Room (may retry later)"
fi

# Fellowship SUT Setup
log "Setting up Fellowship SUT..."
mkdir -p /home/ec2-user/fellowship-sut

# Get SUT bucket from SSM
log "Retrieving SUT bucket from SSM: /classroom/fellowship/sut-bucket"
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --query "Parameter.Value" --output text --region "${AWS_REGION}" 2>&1)
if [ $? -ne 0 ] || [ -z "$SUT_BUCKET" ] || [ "$SUT_BUCKET" = "None" ]; then
    log "ERROR: Failed to get SUT bucket from SSM"
    log "Error: $SUT_BUCKET"
    exit 1
fi
log "SUT bucket: $SUT_BUCKET"

# Download SUT from S3
log "Downloading SUT from S3..."
if ! aws s3 cp "s3://${SUT_BUCKET}/fellowship-sut.tar.gz" /tmp/fellowship-sut.tar.gz --region "${AWS_REGION}" >/dev/null 2>&1 || [ ! -f "/tmp/fellowship-sut.tar.gz" ]; then
    log "ERROR: Failed to download SUT from S3"
    log "Expected location: s3://${SUT_BUCKET}/fellowship-sut.tar.gz"
    exit 1
fi
log "✓ SUT downloaded"

# Extract SUT
log "Extracting SUT..."
if ! tar -xzf /tmp/fellowship-sut.tar.gz -C /home/ec2-user/ 2>/dev/null; then
    log "ERROR: Failed to extract SUT"
    exit 1
fi
rm -f /tmp/fellowship-sut.tar.gz
chown -R ec2-user:ec2-user /home/ec2-user/fellowship-sut
log "✓ SUT extracted"



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
    CADDY_DOMAIN=""
    
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
        # Get domain from instance tags (set by Lambda BEFORE instance creation)
        # With predictable domain names, this should be available immediately
        log "Retrieving HttpsDomain tag from instance tags..."
        for i in {1..6}; do
            CADDY_DOMAIN=$(aws ec2 describe-tags --region "${AWS_REGION}" --filters "Name=resource-id,Values=${INSTANCE_ID}" "Name=key,Values=HttpsDomain" --query "Tags[0].Value" --output text 2>/dev/null || echo "")
            if [ -n "$CADDY_DOMAIN" ] && [ "$CADDY_DOMAIN" != "None" ] && [ "$CADDY_DOMAIN" != "" ]; then
                log "✓ Found Caddy domain from tags: $CADDY_DOMAIN"
                break
            fi
            if [ $i -lt 6 ]; then
                log "  Attempt $i/6: HttpsDomain tag not found yet, waiting 2s..."
                sleep 2
            fi
        done
    else
        log "WARNING: Could not get instance ID after retries"
    fi
    
    # Final check
    if [ -z "$CADDY_DOMAIN" ] || [ "$CADDY_DOMAIN" = "None" ] || [ "$CADDY_DOMAIN" = "" ]; then
        log "ERROR: Caddy domain not found - cannot deploy AWS Fellowship SUT without a valid domain"
        log "  Ensure HttpsDomain tag is set before instance bootstrap"
        exit 1
    fi
fi

# Enforce domain presence for AWS deployment
if [ -z "$CADDY_DOMAIN" ] || [ "$CADDY_DOMAIN" = "None" ] || [ "$CADDY_DOMAIN" = "" ]; then
    log "ERROR: Caddy domain is required for AWS deployment"
    exit 1
fi

# Wait for DNS propagation before starting containers (required for Caddy automatic HTTPS)
PUBLIC_IP_FOR_DNS=$(get_instance_metadata "public-ipv4")
if [ -z "$PUBLIC_IP_FOR_DNS" ]; then
    log "ERROR: Could not retrieve instance public IP for DNS verification"
    exit 1
fi

resolve_domain_ipv4() {
    local domain="$1"
    local resolved_ip

    resolved_ip=$(getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
    if [ -z "$resolved_ip" ]; then
        resolved_ip=$(nslookup "$domain" 2>/dev/null | awk '/^Address: / {print $2}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | tail -1 || true)
    fi

    echo "$resolved_ip"
}

log "Waiting for DNS propagation: ${CADDY_DOMAIN} -> ${PUBLIC_IP_FOR_DNS}"
DNS_MATCHED="false"
for i in {1..30}; do
    RESOLVED_IP=$(resolve_domain_ipv4 "$CADDY_DOMAIN")
    if [ "$RESOLVED_IP" = "$PUBLIC_IP_FOR_DNS" ]; then
        DNS_MATCHED="true"
        log "✓ DNS propagation complete (${CADDY_DOMAIN} resolves to ${RESOLVED_IP})"
        break
    fi

    log "  Attempt $i/30: ${CADDY_DOMAIN} resolves to '${RESOLVED_IP:-unresolved}' (expected ${PUBLIC_IP_FOR_DNS}), waiting 10s..."
    sleep 10
done

if [ "$DNS_MATCHED" != "true" ]; then
    log "ERROR: DNS propagation timeout after 5 minutes"
    log "  ${CADDY_DOMAIN} did not resolve to instance public IP ${PUBLIC_IP_FOR_DNS}"
    log "  Caddy automatic HTTPS cannot succeed until DNS is correct"
    exit 1
fi

# Deploy SUT
log "Deploying SUT..."
if [ ! -f "/home/ec2-user/fellowship-sut/docker-compose.yml" ]; then
    log "ERROR: SUT docker-compose.yml not found"
    exit 1
fi
if [ ! -x "/home/ec2-user/.docker/cli-plugins/docker-compose" ]; then
    log "ERROR: Docker Compose plugin not executable"
    exit 1
fi
# Deploy SUT
log "Deploying SUT..."
if [ ! -f "/home/ec2-user/fellowship-sut/docker-compose.yml" ]; then
    log "ERROR: SUT docker-compose.yml not found"
    exit 1
fi
if [ ! -x "/home/ec2-user/.docker/cli-plugins/docker-compose" ]; then
    log "ERROR: Docker Compose plugin not executable"
    exit 1
fi

# Create .env file for docker-compose BEFORE deployment
# This ensures all environment variables are persistently available
log "Creating .env file with deployment configuration for docker-compose..."
cat > /home/ec2-user/fellowship-sut/.env << EOF
# Docker Compose environment file
# Automatically generated during instance setup

# Domain configuration for Caddy reverse proxy
CADDY_DOMAIN=${CADDY_DOMAIN}
EOF

# Verify .env file was created and is readable
if [ ! -f /home/ec2-user/fellowship-sut/.env ]; then
    log "ERROR: Failed to create .env file"
    exit 1
fi

# Make sure file is owned by ec2-user
chown ec2-user:ec2-user /home/ec2-user/fellowship-sut/.env
chmod 644 /home/ec2-user/fellowship-sut/.env

log "✓ Created /home/ec2-user/fellowship-sut/.env with CADDY_DOMAIN=${CADDY_DOMAIN}"

# Verify .env file contents
log "Verifying .env file contents:"
cat /home/ec2-user/fellowship-sut/.env | sed 's/^/  /'

# Additional safety check: ensure CADDY_DOMAIN is not empty
if [ -z "$CADDY_DOMAIN" ]; then
    log "ERROR: CADDY_DOMAIN is empty - docker-compose will not start properly"
    exit 1
fi

# Deploy SUT containers using docker-compose
# Note: Pass environment variables both via .env file AND explicit exports for maximum compatibility
log "Starting SUT containers..."
log "  CADDY_DOMAIN: ${CADDY_DOMAIN}"

# Use cd to set working directory, then docker compose will auto-load .env
DEPLOY_OUTPUT=$(run_as_ec2user_docker "cd ~/fellowship-sut && docker compose up -d 2>&1" 2>&1)
DEPLOY_EXIT_CODE=$?

if [ $DEPLOY_EXIT_CODE -ne 0 ]; then
    log "ERROR: Failed to start SUT containers (exit code: $DEPLOY_EXIT_CODE)"
    log "Docker Compose output:"
    echo "$DEPLOY_OUTPUT" | sed 's/^/  /'
    log "Checking Docker logs for more information..."
    run_as_ec2user_docker "cd ~/fellowship-sut && docker compose logs" 2>&1 | tail -50 | sed 's/^/  /'
    exit 1
fi

log "✓ Docker Compose started successfully"
log "Waiting for containers to be in running state..."

# Wait for containers to be running (up to 60 seconds)
CONTAINER_WAIT_COUNT=0
while [ $CONTAINER_WAIT_COUNT -lt 12 ]; do
    RUNNING_CONTAINERS=$(run_as_ec2user_docker "cd ~/fellowship-sut && docker compose ps -q --status running 2>/dev/null | wc -l" 2>/dev/null || echo "0")
    EXPECTED_CONTAINERS=3
    
    if [ "$RUNNING_CONTAINERS" -ge "$EXPECTED_CONTAINERS" ]; then
        log "✓ All required containers running ($RUNNING_CONTAINERS/$EXPECTED_CONTAINERS)"
        break
    fi
    
    log "  Waiting for containers... ($RUNNING_CONTAINERS/$EXPECTED_CONTAINERS running, attempt $((CONTAINER_WAIT_COUNT + 1))/12)"
    sleep 5
    CONTAINER_WAIT_COUNT=$((CONTAINER_WAIT_COUNT + 1))
done

# Wait for backend health check to pass (up to 20 attempts * 3 seconds = 60 seconds)
log "Waiting for backend service to be healthy..."
BACKEND_HEALTH_COUNT=0
BACKEND_READY=false
while [ $BACKEND_HEALTH_COUNT -lt 20 ]; do
    BACKEND_STATUS=$(run_as_ec2user_docker "cd ~/fellowship-sut && docker compose ps backend --format json 2>/dev/null" | grep -o '"State":"running"' || echo "")
    if [ -n "$BACKEND_STATUS" ]; then
        log "✓ Backend container is running"
        BACKEND_READY=true
        break
    fi
    
    log "  Waiting for backend to be ready... (attempt $((BACKEND_HEALTH_COUNT + 1))/20)"
    sleep 3
    BACKEND_HEALTH_COUNT=$((BACKEND_HEALTH_COUNT + 1))
done

# Wait for frontend to compile and start (React dev server, up to 60 seconds)
log "Waiting for frontend to compile and start..."
FRONTEND_WAIT_COUNT=0
FRONTEND_READY=false
while [ $FRONTEND_WAIT_COUNT -lt 20 ]; do
    FRONTEND_LOGS=$(run_as_ec2user_docker "cd ~/fellowship-sut && docker compose logs frontend 2>&1" | grep -iE "compiled successfully|webpack compiled|app is running on" || echo "")
    if [ -n "$FRONTEND_LOGS" ]; then
        log "✓ Frontend is ready"
        FRONTEND_READY=true
        break
    fi
    
    log "  Waiting for frontend compilation... (attempt $((FRONTEND_WAIT_COUNT + 1))/20)"
    sleep 3
    FRONTEND_WAIT_COUNT=$((FRONTEND_WAIT_COUNT + 1))
done

# Verify environment variables made it to Caddy container
log "Verifying environment variables in Caddy container..."
CADDY_ENV=$(run_as_ec2user_docker "cd ~/fellowship-sut && docker inspect fellowship-caddy --format='{{.Config.Env}}' 2>/dev/null | grep -o 'CADDY_DOMAIN=[^[:space:]]*' || echo 'NOT FOUND'" 2>/dev/null)
if [ -n "$CADDY_ENV" ] && [ "$CADDY_ENV" != "NOT FOUND" ]; then
    log "✓ CADDY_DOMAIN verified in container: $CADDY_ENV"
else
    log "WARNING: CADDY_DOMAIN not found in container environment"
    log "  This may cause connection issues"
    log "  Container environment (first 20 vars):"
    run_as_ec2user_docker "cd ~/fellowship-sut && docker exec fellowship-caddy env 2>/dev/null | head -20" 2>/dev/null | sed 's/^/    /' || true
fi

# Final container status check
log "Final container status:"
run_as_ec2user_docker "cd ~/fellowship-sut && docker compose ps" 2>&1 | sed 's/^/  /'

# Final status
PUBLIC_IP=$(get_instance_metadata "public-ipv4")
[ -z "$PUBLIC_IP" ] && PUBLIC_IP="N/A"
log "=========================================="
log "Setup Complete"
log "=========================================="
log "Public IP: $PUBLIC_IP"
log "Jenkins: http://${PUBLIC_IP}:8080"
log "SUT: http://${PUBLIC_IP}/"
log "MailHog UI: http://${PUBLIC_IP}:8025"
log "=========================================="
