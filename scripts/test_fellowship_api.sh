#!/bin/bash
# Test script for Fellowship Quest Tracker API
# Usage: ./scripts/test_fellowship_api.sh <instance-ip-or-domain>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <instance-ip-or-domain>"
    echo "Example: $0 54.247.143.240"
    exit 1
fi

INSTANCE_URL="$1"
BASE_URL="http://${INSTANCE_URL}"

echo "=========================================="
echo "Testing Fellowship Quest Tracker API"
echo "Instance: $INSTANCE_URL"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo "1. Testing Health Check..."
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/health" || echo "ERROR")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}✗ Health check failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 2: API Info
echo "2. Testing API Info..."
API_INFO=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api" || echo "ERROR")
HTTP_CODE=$(echo "$API_INFO" | tail -n1)
BODY=$(echo "$API_INFO" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ API info endpoint works${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}✗ API info failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 3: Login (Invalid Credentials)
echo "3. Testing Login with Invalid Credentials..."
LOGIN_INVALID=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"invalid","password":"wrong"}' \
    -c /tmp/fellowship_cookies.txt || echo "ERROR")
HTTP_CODE=$(echo "$LOGIN_INVALID" | tail -n1)
BODY=$(echo "$LOGIN_INVALID" | sed '$d')

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Invalid login correctly rejected (HTTP 401)${NC}"
    echo "Response: $BODY"
else
    echo -e "${YELLOW}⚠ Unexpected response (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 4: Login (Valid Credentials - Frodo)
echo "4. Testing Login with Valid Credentials (frodo_baggins)..."
LOGIN_VALID=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"frodo_baggins","password":"fellowship123"}' \
    -c /tmp/fellowship_cookies.txt || echo "ERROR")
HTTP_CODE=$(echo "$LOGIN_VALID" | tail -n1)
BODY=$(echo "$LOGIN_VALID" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Login successful${NC}"
    echo "Response: $BODY"
    # Extract user info
    USERNAME=$(echo "$BODY" | grep -o '"username":"[^"]*"' | cut -d'"' -f4 || echo "")
    if [ -n "$USERNAME" ]; then
        echo "Logged in as: $USERNAME"
    fi
else
    echo -e "${RED}✗ Login failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
    echo ""
    echo "Expected credentials:"
    echo "  Username: frodo_baggins"
    echo "  Password: fellowship123"
fi
echo ""

# Test 5: Get Current User (requires session)
echo "5. Testing Get Current User (requires session)..."
CURRENT_USER=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/auth/me" \
    -b /tmp/fellowship_cookies.txt || echo "ERROR")
HTTP_CODE=$(echo "$CURRENT_USER" | tail -n1)
BODY=$(echo "$CURRENT_USER" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Current user endpoint works${NC}"
    echo "Response: $BODY"
elif [ "$HTTP_CODE" = "401" ]; then
    echo -e "${YELLOW}⚠ Not authenticated (expected if login failed)${NC}"
else
    echo -e "${RED}✗ Unexpected response (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 6: Get Quests (requires authentication)
echo "6. Testing Get Quests (requires authentication)..."
QUESTS=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/quests/" \
    -b /tmp/fellowship_cookies.txt || echo "ERROR")
HTTP_CODE=$(echo "$QUESTS" | tail -n1)
BODY=$(echo "$QUESTS" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Quests endpoint works${NC}"
    QUEST_COUNT=$(echo "$BODY" | grep -o '"id"' | wc -l || echo "0")
    echo "Found $QUEST_COUNT quest(s)"
    echo "Response preview: $(echo "$BODY" | head -c 200)..."
elif [ "$HTTP_CODE" = "401" ]; then
    echo -e "${YELLOW}⚠ Not authenticated (expected if login failed)${NC}"
else
    echo -e "${RED}✗ Unexpected response (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 7: Get Members (public endpoint)
echo "7. Testing Get Members (public endpoint)..."
MEMBERS=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/members/" || echo "ERROR")
HTTP_CODE=$(echo "$MEMBERS" | tail -n1)
BODY=$(echo "$MEMBERS" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Members endpoint works${NC}"
    MEMBER_COUNT=$(echo "$BODY" | grep -o '"id"' | wc -l || echo "0")
    echo "Found $MEMBER_COUNT member(s)"
    echo "Response preview: $(echo "$BODY" | head -c 200)..."
else
    echo -e "${RED}✗ Members endpoint failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 8: Get Locations (public endpoint)
echo "8. Testing Get Locations (public endpoint)..."
LOCATIONS=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/locations/" || echo "ERROR")
HTTP_CODE=$(echo "$LOCATIONS" | tail -n1)
BODY=$(echo "$LOCATIONS" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Locations endpoint works${NC}"
    LOCATION_COUNT=$(echo "$BODY" | grep -o '"id"' | wc -l || echo "0")
    echo "Found $LOCATION_COUNT location(s)"
    echo "Response preview: $(echo "$BODY" | head -c 200)..."
else
    echo -e "${RED}✗ Locations endpoint failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 9: Frontend Accessibility
echo "9. Testing Frontend Accessibility..."
FRONTEND=$(curl -s -w "\n%{http_code}" "${BASE_URL}/" -o /dev/null || echo "ERROR")
HTTP_CODE=$(echo "$FRONTEND" | tail -n1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "304" ]; then
    echo -e "${GREEN}✓ Frontend is accessible${NC}"
else
    echo -e "${RED}✗ Frontend not accessible (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Instance URL: $BASE_URL"
echo ""
echo "Available Test Users:"
echo "  - frodo_baggins / fellowship123"
echo "  - samwise_gamgee / fellowship123"
echo "  - aragorn / fellowship123"
echo "  - legolas / fellowship123"
echo "  - gimli / fellowship123"
echo "  - gandalf / fellowship123"
echo ""
echo "API Endpoints:"
echo "  - GET  ${BASE_URL}/api/health"
echo "  - GET  ${BASE_URL}/api"
echo "  - POST ${BASE_URL}/api/auth/login"
echo "  - GET  ${BASE_URL}/api/auth/me"
echo "  - GET  ${BASE_URL}/api/quests/"
echo "  - GET  ${BASE_URL}/api/members/"
echo "  - GET  ${BASE_URL}/api/locations/"
echo ""
echo "Swagger Documentation:"
echo "  - ${BASE_URL}/api/swagger/"
echo ""
