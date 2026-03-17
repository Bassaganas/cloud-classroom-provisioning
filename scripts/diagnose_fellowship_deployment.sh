#!/bin/bash
# Comprehensive diagnostics for Fellowship SUT deployment
# Run this on the EC2 instance to verify everything is working

set -e

echo "=========================================="
echo "Fellowship SUT Deployment Diagnostics"
echo "=========================================="
echo ""

# Get relevant metadata
CURRENT_USER=$(whoami)
INSTANCE_ID=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo "N/A")
PUBLIC_IP=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
PRIVATE_IP=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/local-ipv4 2>/dev/null || echo "N/A")

echo "1. Instance Information"
echo "  Current User: $CURRENT_USER"
echo "  Instance ID: $INSTANCE_ID"
echo "  Public IP: $PUBLIC_IP"
echo "  Private IP: $PRIVATE_IP"
echo ""

# Check if fellowship-sut directory exists
echo "2. Directory Structure"
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    echo "  ✓ Fellowship SUT directory exists: /home/ec2-user/fellowship-sut"
    echo "    Contents:"
    ls -la /home/ec2-user/fellowship-sut/ 2>/dev/null | head -15
else
    echo "  ✗ Fellowship SUT directory NOT found at /home/ec2-user/fellowship-sut"
    echo "    Listing /home/ec2-user/:"
    ls -la /home/ec2-user/ 2>/dev/null | head -15
fi
echo ""

# Check Docker
echo "3. Docker Status"
if command -v docker >/dev/null 2>&1; then
    echo "  ✓ Docker executable found"
    DOCKER_VERSION=$(docker --version 2>/dev/null || echo "Unknown")
    echo "    Version: $DOCKER_VERSION"
else
    echo "  ✗ Docker executable NOT found"
fi
echo ""

# Check Docker Compose
echo "4. Docker Compose Status"
if command -v docker-compose >/dev/null 2>&1; then
    echo "  ✓ docker-compose (standalone) found in PATH"
    docker-compose --version 2>/dev/null || echo "    (Could not get version)"
elif [ -x "/home/ec2-user/.docker/cli-plugins/docker-compose" ]; then
    echo "  ✓ docker-compose plugin found for ec2-user"
    su - ec2-user -c "docker compose --version" 2>/dev/null || echo "    (Could not get version)"
else
    echo "  ✗ Docker Compose not found"
    echo "    Checked paths:"
    echo "      - docker-compose in PATH: $(command -v docker-compose 2>/dev/null || echo 'Not found')"
    echo "      - plugin at ~/.docker/cli-plugins/: $([ -x "/home/ec2-user/.docker/cli-plugins/docker-compose" ] && echo 'Found' || echo 'Not found')"
fi
echo ""

# Check containers (as ec2-user)
echo "5. Docker Containers"
echo "  Attempting to list containers as ec2-user..."
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    echo ""
    su - ec2-user << 'EOFUSER'
cd ~/fellowship-sut 2>/dev/null || { echo "  ✗ Could not cd to ~/fellowship-sut"; exit 1; }
echo "  ✓ Switched to /home/ec2-user/fellowship-sut"
echo ""
echo "  Container status:"
docker compose ps 2>/dev/null || { echo "    ✗ docker compose ps failed"; exit 1; }
echo ""
echo "  Container details (JSON):"
docker compose ps -a 2>/dev/null | head -5
EOFUSER
else
    echo "  ✗ Cannot check containers - SUT directory not found"
fi
echo ""

# Check port bindings
echo "6. Port Bindings"
echo "  Checking if Caddy is listening on port 80..."
if netstat -tuln 2>/dev/null | grep -q ":80 "; then
    echo "  ✓ Port 80 is listening"
    netstat -tuln 2>/dev/null | grep ":80" || echo "    (netstat output not available)"
elif ss -tuln 2>/dev/null | grep -q ":80 "; then
    echo "  ✓ Port 80 is listening"
    ss -tuln 2>/dev/null | grep ":80" || echo "    (ss output not available)"
else
    echo "  ✗ Port 80 is NOT listening"
fi
echo "  Checking if Caddy is listening on port 443..."
if netstat -tuln 2>/dev/null | grep -q ":443 "; then
    echo "  ✓ Port 443 is listening"
    netstat -tuln 2>/dev/null | grep ":443" || echo "    (netstat output not available)"
elif ss -tuln 2>/dev/null | grep -q ":443 "; then
    echo "  ✓ Port 443 is listening"
    ss -tuln 2>/dev/null | grep ":443" || echo "    (ss output not available)"
else
    echo "  ✗ Port 443 is NOT listening"
fi
echo ""

# Test local connectivity
echo "7. Local Connectivity Tests"
echo "  Testing HTTP on localhost:80..."
if curl -s --max-time 3 http://localhost/ >/dev/null 2>&1; then
    echo "  ✓ HTTP localhost:80 is responding"
    echo "    Response preview:"
    curl -s --max-time 3 http://localhost/ 2>/dev/null | head -5 || echo "    (Could not get response)"
else
    echo "  ✗ HTTP localhost:80 is NOT responding"
fi
echo ""
echo "  Testing HTTPS on localhost:443..."
if curl -k -s --max-time 5 https://localhost/ >/dev/null 2>&1; then
    echo "  ✓ HTTPS localhost:443 is responding"
    echo "    Response preview:"
    curl -k -s --max-time 5 https://localhost/ 2>/dev/null | head -5 || echo "    (Could not get response)"
else
    echo "  ✗ HTTPS localhost:443 is NOT responding"
fi
echo ""

# Check Caddy logs
echo "8. Caddy Container Logs"
echo "  Last 20 lines from Caddy container:"
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    su - ec2-user -c "cd ~/fellowship-sut && docker compose logs caddy 2>&1 | tail -20" 2>/dev/null || echo "  ✗ Could not get Caddy logs"
else
    echo "  ✗ Cannot get logs - SUT directory not found"
fi
echo ""

# Check Backend logs for API
echo "9. Backend Container Logs"
echo "  Last 15 lines from Backend container:"
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    su - ec2-user -c "cd ~/fellowship-sut && docker compose logs backend 2>&1 | tail -15" 2>/dev/null || echo "  ✗ Could not get Backend logs"
else
    echo "  ✗ Cannot get logs - SUT directory not found"
fi
echo ""

# Check Frontend logs
echo "10. Frontend Container Logs"
echo "  Last 15 lines from Frontend container:"
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    su - ec2-user -c "cd ~/fellowship-sut && docker compose logs frontend 2>&1 | tail -15" 2>/dev/null || echo "  ✗ Could not get Frontend logs"
else
    echo "  ✗ Cannot get logs - SUT directory not found"
fi
echo ""

# Check Caddy configuration
echo "11. Caddy Configuration"
CADDY_CONFIG_PATH="/home/ec2-user/fellowship-sut/caddy/Caddyfile"
echo "  Config path: $CADDY_CONFIG_PATH"

if [ -f "$CADDY_CONFIG_PATH" ]; then
    echo "  ✓ Caddy config found"
    echo "    Contents:"
    cat "$CADDY_CONFIG_PATH" 2>/dev/null | head -20
else
    echo "  ✗ Selected Caddy config NOT found: $SELECTED_CADDY_FILE"
fi
echo ""

# Check environment used for deployment
echo "12. Deployment Environment"
if [ -d "/home/ec2-user/fellowship-sut" ]; then
    echo "  Checking docker-compose.yml for environment variables..."
    grep -A 5 "environment:" /home/ec2-user/fellowship-sut/docker-compose.yml 2>/dev/null | head -10 || echo "  (Could not parse environment section)"
else
    echo "  ✗ Cannot check - SUT directory not found"
fi
echo ""

echo "13. Domain DNS Verification"
ENV_FILE="/home/ec2-user/fellowship-sut/.env"
if [ -f "$ENV_FILE" ]; then
    CADDY_DOMAIN_VALUE=$(grep '^CADDY_DOMAIN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
    if [ -n "$CADDY_DOMAIN_VALUE" ]; then
        echo "  Found CADDY_DOMAIN in .env: $CADDY_DOMAIN_VALUE"

        RESOLVED_IP=$(getent ahostsv4 "$CADDY_DOMAIN_VALUE" 2>/dev/null | awk '{print $1}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
        if [ -z "$RESOLVED_IP" ]; then
            RESOLVED_IP=$(nslookup "$CADDY_DOMAIN_VALUE" 2>/dev/null | awk '/^Address: / {print $2}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | tail -1 || true)
        fi

        if [ -n "$RESOLVED_IP" ]; then
            echo "  DNS resolves to: $RESOLVED_IP"
            if [ "$PUBLIC_IP" = "$RESOLVED_IP" ]; then
                echo "  ✓ DNS matches instance public IP"
            else
                echo "  ✗ DNS does not match instance public IP ($PUBLIC_IP)"
                echo "    Next step: update DNS A record for $CADDY_DOMAIN_VALUE to $PUBLIC_IP and wait for propagation"
            fi
        else
            echo "  ✗ Domain does not currently resolve"
            echo "    Next step: create/fix DNS A record for $CADDY_DOMAIN_VALUE -> $PUBLIC_IP"
        fi
    else
        echo "  CADDY_DOMAIN is empty in .env (local HTTP mode or incomplete deployment)"
    fi
else
    echo "  .env file not found at $ENV_FILE"
fi
echo ""

# Summary
echo "=========================================="
echo "Diagnostics Summary"
echo "=========================================="
echo ""
echo "Next steps if issues are found:"
echo "1. If containers aren't running: Check setup logs at /var/log/user-data.log"
echo "2. If port 80 isn't listening: Check Caddy logs above for binding errors"
echo "3. If HTTPS localhost fails: Check Caddy logs for ACME/certificate errors"
echo "4. If localhost isn't responding: Restart Caddy with: docker compose restart caddy"
echo "5. If domain isn't accessible: Check security groups allow HTTP/HTTPS (80, 443)"
echo "6. If certificate issuance fails: Ensure DNS A record points to this instance public IP"
echo "7. If certificate still not issued: wait 2-5 minutes and retry after DNS propagation"
echo ""
echo "Useful commands to run manually:"
echo "  cd /home/ec2-user/fellowship-sut"
echo "  docker compose ps                          # Check container status"
echo "  docker compose logs -f caddy                # Follow Caddy logs"
echo "  docker compose logs -f backend              # Follow backend logs"
echo "  curl -v http://localhost/                   # Test local connectivity"
echo "  curl -vk https://localhost/                 # Test local HTTPS/certificate path"
echo "  docker compose restart caddy                # Restart Caddy if domain changed"
echo ""
echo "=========================================="
