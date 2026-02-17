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

# DevOps Escape Room stack (Jenkins + MailHog)
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

su - ec2-user -c "cd ~/devops-escape-room && docker compose up -d"

echo "DevOps Escape Room setup completed"
echo "Jenkins: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080"
echo "MailHog: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8025"
