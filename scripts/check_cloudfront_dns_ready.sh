#!/bin/bash

# Check if DNS is ready for CloudFront to accept the aliases
# CloudFront validates DNS from multiple locations, so we check from different resolvers

set -e

echo "🔍 Checking DNS Readiness for CloudFront"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DOMAIN="testingfantasy.com"
WWW_DOMAIN="www.testingfantasy.com"
EXPECTED_CLOUDFRONT="d14o6b6v4fsw4f.cloudfront.net"

echo "Expected CloudFront domain: $EXPECTED_CLOUDFRONT"
echo ""

# Check from different DNS resolvers
RESOLVERS=(
    "8.8.8.8:Google"
    "1.1.1.1:Cloudflare"
    "208.67.222.222:OpenDNS"
)

echo "📋 Checking DNS Resolution from Multiple Resolvers:"
echo "---------------------------------------------------"

ALL_CORRECT=true

for resolver_info in "${RESOLVERS[@]}"; do
    IFS=':' read -r ip name <<< "$resolver_info"
    
    # Check root domain
    ROOT_RESULT=$(dig +short "$DOMAIN" @"$ip" 2>/dev/null | head -1 || echo "")
    WWW_RESULT=$(dig +short "$WWW_DOMAIN" @"$ip" 2>/dev/null | head -1 || echo "")
    
    if [ -n "$ROOT_RESULT" ]; then
        # Check if it resolves to CloudFront IP (indirect check)
        if [[ "$ROOT_RESULT" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo -e "${GREEN}✅ $name ($ip): $DOMAIN -> $ROOT_RESULT (CloudFront IP)${NC}"
        else
            echo -e "${YELLOW}⚠️  $name ($ip): $DOMAIN -> $ROOT_RESULT${NC}"
            ALL_CORRECT=false
        fi
    else
        echo -e "${RED}❌ $name ($ip): $DOMAIN -> No result${NC}"
        ALL_CORRECT=false
    fi
    
    # Check www domain
    if [[ "$WWW_RESULT" == *"$EXPECTED_CLOUDFRONT"* ]] || [[ "$WWW_RESULT" == "$DOMAIN"* ]]; then
        echo -e "${GREEN}✅ $name ($ip): $WWW_DOMAIN -> $WWW_RESULT${NC}"
    elif [ -n "$WWW_RESULT" ]; then
        echo -e "${YELLOW}⚠️  $name ($ip): $WWW_DOMAIN -> $WWW_RESULT${NC}"
        if [[ "$WWW_RESULT" != *"$EXPECTED_CLOUDFRONT"* ]]; then
            ALL_CORRECT=false
        fi
    else
        echo -e "${RED}❌ $name ($ip): $WWW_DOMAIN -> No result${NC}"
        ALL_CORRECT=false
    fi
done

echo ""
echo "📋 Checking Route 53 Authoritative DNS:"
echo "---------------------------------------------------"

# Check from Route 53 name servers
ROUTE53_NS="ns-1140.awsdns-14.org"
ROOT_AUTHORITATIVE=$(dig +short "$DOMAIN" @"$ROUTE53_NS" 2>/dev/null | head -1 || echo "")
WWW_AUTHORITATIVE=$(dig +short "$WWW_DOMAIN" @"$ROUTE53_NS" 2>/dev/null | head -1 || echo "")

if [ -n "$ROOT_AUTHORITATIVE" ]; then
    echo -e "${GREEN}✅ Route 53 NS: $DOMAIN -> $ROOT_AUTHORITATIVE${NC}"
else
    echo -e "${RED}❌ Route 53 NS: $DOMAIN -> No result${NC}"
    ALL_CORRECT=false
fi

if [[ "$WWW_AUTHORITATIVE" == *"$EXPECTED_CLOUDFRONT"* ]] || [[ "$WWW_AUTHORITATIVE" == "$DOMAIN"* ]]; then
    echo -e "${GREEN}✅ Route 53 NS: $WWW_DOMAIN -> $WWW_AUTHORITATIVE${NC}"
else
    echo -e "${YELLOW}⚠️  Route 53 NS: $WWW_DOMAIN -> $WWW_AUTHORITATIVE${NC}"
    if [[ "$WWW_AUTHORITATIVE" != *"$EXPECTED_CLOUDFRONT"* ]]; then
        ALL_CORRECT=false
    fi
fi

echo ""
echo "========================================="

if [ "$ALL_CORRECT" = true ]; then
    echo -e "${GREEN}✅ DNS looks correct from all resolvers!${NC}"
    echo ""
    echo "⏳ However, CloudFront's validation can still take:"
    echo "   - Minimum: 5-10 minutes after DNS change"
    echo "   - Typical: 15-30 minutes"
    echo "   - Maximum: Up to 1 hour (rare)"
    echo ""
    echo "💡 Try adding the domain again in CloudFront console."
    echo "   If it still fails, wait another 15 minutes and retry."
else
    echo -e "${YELLOW}⚠️  Some DNS resolvers show incorrect values${NC}"
    echo ""
    echo "⏳ Wait for DNS propagation:"
    echo "   - TTL is 500 seconds (~8 minutes)"
    echo "   - Full propagation: 15-30 minutes"
    echo "   - CloudFront validation: Additional 5-15 minutes"
    echo ""
    echo "💡 Wait at least 15-30 minutes total before retrying."
fi

echo ""
echo "🔧 If it still fails after 30 minutes:"
echo "   1. Verify Route 53 records are correct"
echo "   2. Check for any other CloudFront distributions with these aliases"
echo "   3. Try using Terraform instead of the console"
echo ""

