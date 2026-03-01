#!/bin/bash

# Script to rebuild and test the fellowship SUT with CORS fixes

set -e

cd "$(dirname "$0")"

echo "🔧 Stopping existing containers..."
docker-compose down

echo "🏗️ Rebuilding images with CORS fixes..."
docker-compose build --no-cache backend frontend

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready (15 seconds)..."
sleep 15

echo "✅ Services are running!"
echo ""
echo "📋 Service URLs:"
echo "  • Frontend (dev): http://localhost:3000"
echo "  • Backend API: http://localhost:5000/api"
echo "  • Caddy Proxy: http://localhost/api"
echo ""
echo "🧪 Testing CORS connectivity..."
echo ""

# Test backend health
echo "Testing backend health..."
curl -s -i -X GET http://localhost:5000/api/health | head -5

echo ""
echo "Testing OPTIONS preflight request to backend..."
curl -s -i -X OPTIONS http://localhost:5000/api/auth/login \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" | head -10

echo ""
echo "Testing API endpoint through backend..."
curl -s -i -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:3000" \
  -d '{"username":"test","password":"test"}' | head -10

echo ""
echo "✨ CORS fixes applied! The frontend should now connect properly."
echo ""
echo "If you still see CORS errors:"
echo "  1. Check browser DevTools Console for detailed error messages"
echo "  2. Verify backend logs: docker logs fellowship-backend"
echo "  3. Verify frontend logs: docker logs fellowship-frontend"
echo "  4. Verify Caddy logs: docker logs fellowship-caddy"
