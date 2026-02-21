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

log "=========================================="
log "Fellowship Setup Script Started"
log "=========================================="

# Get AWS region with retries and fallback
AWS_REGION=""
for i in {1..5}; do
    AWS_REGION=$(curl -s --max-time 5 --connect-timeout 2 http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "")
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
if su - ec2-user -c "cd ~/devops-escape-room && docker compose up -d" >/dev/null 2>&1; then
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
log "Starting SUT containers..."
DEPLOY_OUTPUT=$(su - ec2-user -c "cd ~/fellowship-sut && docker compose up -d 2>&1")
DEPLOY_EXIT_CODE=$?
if [ $DEPLOY_EXIT_CODE -ne 0 ]; then
    log "ERROR: Failed to start SUT containers (exit code: $DEPLOY_EXIT_CODE)"
    log "Docker Compose output: $DEPLOY_OUTPUT"
    log "Checking Docker Compose logs..."
    su - ec2-user -c "cd ~/fellowship-sut && docker compose logs" 2>&1 | tail -30 || true
    exit 1
fi
log "Waiting for containers to start and become healthy..."
# Wait for containers to be running
for i in {1..12}; do
    CONTAINER_COUNT=$(su - ec2-user -c "cd ~/fellowship-sut && docker compose ps -q --status running | wc -l" 2>/dev/null || echo "0")
    if [ "$CONTAINER_COUNT" -ge "3" ]; then
        log "All containers running ($CONTAINER_COUNT/3)"
        break
    fi
    log "Waiting for containers... ($i/12)"
    sleep 5
done

# Wait for backend health check to pass
log "Waiting for backend to be healthy..."
for i in {1..20}; do
    BACKEND_HEALTH=$(su - ec2-user -c "cd ~/fellowship-sut && docker compose ps backend --format json" 2>/dev/null | grep -o '"Health":"healthy"' || echo "")
    if [ -n "$BACKEND_HEALTH" ]; then
        log "Backend is healthy"
        break
    fi
    sleep 3
done

# Wait for frontend to be ready (React dev server takes time to compile)
log "Waiting for frontend to compile and start..."
for i in {1..30}; do
    FRONTEND_READY=$(su - ec2-user -c "cd ~/fellowship-sut && docker compose logs frontend 2>&1 | grep -i 'compiled\|webpack compiled\|Compiled successfully' | tail -1" || echo "")
    if [ -n "$FRONTEND_READY" ]; then
        log "Frontend is ready"
        break
    fi
    sleep 2
done

# Final verification
CONTAINER_COUNT=$(su - ec2-user -c "cd ~/fellowship-sut && docker compose ps -q --status running | wc -l" 2>/dev/null || echo "0")
if [ "$CONTAINER_COUNT" -ge "3" ]; then
    log "✓ SUT deployed successfully ($CONTAINER_COUNT container(s) running)"
else
    log "WARNING: Only $CONTAINER_COUNT container(s) running (expected 3)"
    log "Container status:"
    su - ec2-user -c "cd ~/fellowship-sut && docker compose ps" 2>&1 || true
fi

# Final status
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
log "=========================================="
log "Setup Complete"
log "=========================================="
log "Public IP: $PUBLIC_IP"
log "Jenkins: http://${PUBLIC_IP}:8080"
log "SUT: http://${PUBLIC_IP}/"
log "MailHog UI: http://${PUBLIC_IP}:8025"
log "=========================================="
