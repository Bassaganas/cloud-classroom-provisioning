#!/bin/bash

# Test script to verify CADDY_DOMAIN is properly passed to Caddy container
# Usage: ./test_caddy_domain.sh <domain>
# Example: ./test_caddy_domain.sh fellowship-tut2-pool-0.fellowship.testingfantasy.com

set -e

DOMAIN="${1:-fellowship-tut2-pool-0.fellowship.testingfantasy.com}"
SUT_PATH="${2:-${HOME}/fellowship-sut}"

echo "=========================================="
echo "Testing CADDY_DOMAIN Configuration"
echo "=========================================="
echo "Domain: $DOMAIN"
echo "SUT Path: $SUT_PATH"
echo ""

if [ ! -d "$SUT_PATH" ]; then
    echo "ERROR: SUT directory not found at: $SUT_PATH"
    exit 1
fi

cd "$SUT_PATH"

echo "[1/5] Creating .env file..."
cat > .env << EOF
CADDY_DOMAIN=${DOMAIN}
EOF
echo "✓ Created .env with CADDY_DOMAIN=${DOMAIN}"
echo ""

echo "[2/5] Checking .env file..."
echo "Content:"
cat .env | sed 's/^/  /'
echo ""

echo "[3/5] Restarting containers (down + up)..."
docker compose down
docker compose up -d
echo "✓ Containers restarted"
echo ""

echo "[4/5] Waiting for Caddy to start..."
sleep 5
echo "✓ Waiting complete"
echo ""

echo "[5/5] Verifying CADDY_DOMAIN in container..."
echo ""

# Check if CADDY_DOMAIN env var is in the container
CADDY_ENV=$(docker inspect fellowship-caddy --format='{{json .Config.Env}}' 2>/dev/null || echo "")

if echo "$CADDY_ENV" | grep -q "CADDY_DOMAIN"; then
    DOMAIN_IN_CONTAINER=$(echo "$CADDY_ENV" | grep -o 'CADDY_DOMAIN=[^"]*' | cut -d= -f2 || echo "")
    echo "✓ CADDY_DOMAIN found in container environment"
    echo "  Value: $DOMAIN_IN_CONTAINER"
else
    echo "⚠ CADDY_DOMAIN not found in container environment"
    echo "  Container environment:"
    docker exec fellowship-caddy env | grep -i caddy || echo "  (No CADDY variables)"
fi

echo ""
echo "=========================================="
echo "Caddy Logs (last 30 lines):"
echo "=========================================="
docker compose logs caddy 2>&1 | tail -30
echo ""

echo "=========================================="
echo "Port Check:"
echo "=========================================="
echo "Checking which ports Caddy is listening on..."
docker compose exec -T caddy netstat -tlnp 2>/dev/null | grep -E 'LISTEN|tcp' || echo "netstat not available in container"
echo ""

echo "=========================================="
echo "Summary:"
echo "=========================================="
if echo "$CADDY_ENV" | grep -q "CADDY_DOMAIN"; then
    if ! docker compose logs caddy 2>&1 | grep -q "variable is not set"; then
        echo "✓ SUCCESS: CADDY_DOMAIN properly configured!"
        echo "  Check Caddy logs above for domain configuration"
    else
        echo "⚠ CADDY_DOMAIN set but warnings in logs - check above"
    fi
else
    echo "❌ FAILURE: CADDY_DOMAIN not reaching Caddy container"
    echo "   This needs further investigation"
fi
echo ""
