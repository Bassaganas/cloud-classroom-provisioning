#!/bin/bash

# Script to check SUT deployment on an EC2 instance
# Run this from within an SSM session to the instance

set -e

echo "=========================================="
echo "Checking SUT Deployment on Instance"
echo "=========================================="
echo "Instance ID: $(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'N/A')"
echo "Region: $(curl -s http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo 'N/A')"
echo ""

echo "1. Checking User Data Execution..."
echo "-----------------------------------"
if [ -f /var/log/user-data.log ]; then
    echo "✓ User data log exists"
    echo ""
    echo "Last 50 lines of user-data.log:"
    echo "-----------------------------------"
    tail -50 /var/log/user-data.log 2>/dev/null || echo "Could not read log file"
else
    echo "✗ User data log NOT found at /var/log/user-data.log"
    echo "  Checking alternative locations..."
    if [ -f /var/log/cloud-init-output.log ]; then
        echo "  Found cloud-init-output.log instead"
        tail -50 /var/log/cloud-init-output.log
    fi
fi

echo ""
echo "2. Checking SUT Directory..."
echo "-----------------------------------"
if [ -d /home/ec2-user/fellowship-sut ]; then
    echo "✓ SUT directory exists: /home/ec2-user/fellowship-sut"
    echo ""
    echo "Directory contents:"
    ls -la /home/ec2-user/fellowship-sut/ 2>/dev/null || echo "Cannot list directory (permissions?)"
    echo ""
    echo "Checking for docker-compose.yml:"
    if [ -f /home/ec2-user/fellowship-sut/docker-compose.yml ]; then
        echo "  ✓ docker-compose.yml exists"
    else
        echo "  ✗ docker-compose.yml NOT found"
    fi
else
    echo "✗ SUT directory NOT found: /home/ec2-user/fellowship-sut"
    echo ""
    echo "Checking home directory:"
    ls -la /home/ec2-user/ 2>/dev/null | head -20
fi

echo ""
echo "3. Checking Docker..."
echo "-----------------------------------"
if command -v docker &> /dev/null; then
    echo "✓ Docker is installed"
    docker --version
    echo ""
    echo "Docker service status:"
    sudo systemctl status docker --no-pager -l 2>/dev/null | head -10 || echo "Could not check docker service"
    echo ""
    echo "Running containers:"
    sudo docker ps 2>/dev/null || echo "Cannot list containers (permissions?)"
    echo ""
    echo "All containers (including stopped):"
    sudo docker ps -a 2>/dev/null || echo "Cannot list containers"
else
    echo "✗ Docker is NOT installed"
fi

echo ""
echo "4. Checking Docker Compose..."
echo "-----------------------------------"
if command -v docker-compose &> /dev/null; then
    echo "✓ docker-compose (standalone) is installed"
    docker-compose --version
elif [ -f /home/ec2-user/.docker/cli-plugins/docker-compose ]; then
    echo "✓ docker-compose (plugin) is installed"
    /home/ec2-user/.docker/cli-plugins/docker-compose version 2>/dev/null || echo "Plugin exists but may not be executable"
else
    echo "✗ Docker Compose is NOT found"
fi

echo ""
echo "5. Checking SUT Application..."
echo "-----------------------------------"
if [ -d /home/ec2-user/fellowship-sut ]; then
    cd /home/ec2-user/fellowship-sut 2>/dev/null || echo "Cannot cd to SUT directory"
    
    if [ -f docker-compose.yml ]; then
        echo "✓ docker-compose.yml found"
        echo ""
        echo "Checking if services are defined:"
        grep -E "^\s+[a-z-]+:" docker-compose.yml 2>/dev/null | head -10 || echo "Could not parse docker-compose.yml"
        echo ""
        echo "Attempting to check container status (if docker-compose is available):"
        if command -v docker-compose &> /dev/null; then
            cd /home/ec2-user/fellowship-sut && docker-compose ps 2>/dev/null || echo "docker-compose ps failed"
        elif [ -f /home/ec2-user/.docker/cli-plugins/docker-compose ]; then
            cd /home/ec2-user/fellowship-sut && docker compose ps 2>/dev/null || echo "docker compose ps failed"
        fi
    fi
fi

echo ""
echo "6. Checking Network Connectivity..."
echo "-----------------------------------"
echo "Checking if SUT is listening on port 8080:"
sudo netstat -tlnp 2>/dev/null | grep 8080 || sudo ss -tlnp 2>/dev/null | grep 8080 || echo "Port 8080 not listening or cannot check"

echo ""
echo "7. Checking S3 Bucket Access..."
echo "-----------------------------------"
SUT_BUCKET=$(aws ssm get-parameter --name "/classroom/fellowship/sut-bucket" --query "Parameter.Value" --output text --region "$(curl -s http://169.254.169.254/latest/meta-data/placement/region)" 2>/dev/null || echo "")
if [ -n "$SUT_BUCKET" ]; then
    echo "✓ SUT bucket parameter exists: $SUT_BUCKET"
    echo ""
    echo "Checking if bucket is accessible:"
    aws s3 ls "s3://${SUT_BUCKET}/" 2>/dev/null | head -5 || echo "Cannot access S3 bucket (check IAM permissions)"
else
    echo "✗ SUT bucket parameter not found in SSM"
fi

echo ""
echo "8. Checking IAM Role..."
echo "-----------------------------------"
IAM_ROLE=$(curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>/dev/null | head -1 || echo "N/A")
echo "IAM Role: $IAM_ROLE"

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "To check user data script execution:"
echo "  tail -f /var/log/user-data.log"
echo ""
echo "To check if SUT containers are running:"
echo "  cd /home/ec2-user/fellowship-sut && docker compose ps"
echo ""
echo "To manually start SUT (if not running):"
echo "  cd /home/ec2-user/fellowship-sut && docker compose up -d"
echo ""
echo "To check SUT application logs:"
echo "  cd /home/ec2-user/fellowship-sut && docker compose logs"
echo ""
