#!/bin/bash
set -e

# Update and install dependencies
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /home/ec2-user/.docker/cli-plugins/
curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o /home/ec2-user/.docker/cli-plugins/docker-compose
chmod +x /home/ec2-user/.docker/cli-plugins/docker-compose
chown -R ec2-user:ec2-user /home/ec2-user/.docker

# Clone and start Dify as ec2-user
su - ec2-user -c "git clone https://github.com/langgenius/dify.git ~/dify"
su - ec2-user -c "cp ~/dify/docker/.env.example ~/dify/docker/.env"
su - ec2-user -c "cd ~/dify/docker && docker compose up -d"

# Auto-shutdown after 5 minutes
shutdown -h +5

# Remove any existing shutdown jobs
crontab -r

# Add a new shutdown job for 3 hours after every boot
(crontab -l 2>/dev/null; echo "@reboot shutdown -h +180") | crontab - 