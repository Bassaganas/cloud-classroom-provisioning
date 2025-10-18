#!/bin/bash
set -e

# Function to wait for yum lock
wait_for_yum() {
    while sudo fuser /var/run/yum.pid >/dev/null 2>&1; do
        echo "Waiting for other yum process to finish..."
        sleep 5
    done
}

# Wait for any existing yum processes to complete
wait_for_yum

# Update and install dependencies
yum update -y
wait_for_yum
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /home/ec2-user/.docker/cli-plugins/
curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o /home/ec2-user/.docker/cli-plugins/docker-compose
chmod +x /home/ec2-user/.docker/cli-plugins/docker-compose
chown -R ec2-user:ec2-user /home/ec2-user/.docker

# Clone and configure Dify as ec2-user
su - ec2-user -c "git clone https://github.com/langgenius/dify.git ~/dify"
su - ec2-user -c "cp ~/dify/docker/.env.example ~/dify/docker/.env"

# Configure Dify with minimal, documented configuration
cat >> /home/ec2-user/dify/docker/.env << 'EOF'

# ===== MINIMAL DIFY CONFIGURATION =====

# System language (officially documented in .env.example)
LANG=en_US.UTF-8

# Frontend configuration for nginx proxy
NEXT_PUBLIC_API_PREFIX=/console/api
NEXT_PUBLIC_PUBLIC_API_PREFIX=/v1

EOF

# Start Dify services
su - ec2-user -c "cd ~/dify/docker && docker compose up -d"

# Wait for services to be ready
echo "Waiting for Dify services to start..."
sleep 120

echo "Dify setup completed successfully"
echo "Access Dify at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "Complete the setup through the web interface"