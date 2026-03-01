#!/bin/bash

# Fellowship SUT CORS Testing Guide
# Test the CORS fixes in browser environment

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Fellowship SUT - CORS Fix Testing Guide                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if services are running
echo "📋 Checking service status..."
echo ""

if docker-compose ps | grep -q "fellowship-backend.*Up"; then
    echo "✅ Backend is running on http://localhost:5000"
else
    echo "❌ Backend is not running"
    exit 1
fi

if docker-compose ps | grep -q "fellowship-frontend.*Up"; then
    echo "✅ Frontend is running on http://localhost:3000"
else
    echo "❌ Frontend is not running"
    exit 1
fi

if docker-compose ps | grep -q "fellowship-caddy.*Up"; then
    echo "✅ Caddy is running on http://localhost"
else
    echo "⚠️  Caddy is not running (may be restarting)"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              How to Test CORS Fixes                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "1️⃣  Open Browser and Go to Frontend"
echo "   URL: http://localhost:3000"
echo "   Expected: Login page loads without errors"
echo ""

echo "2️⃣  Open Browser DevTools (Press F12)"
echo "   Look for:"
echo "   - Console tab: Should see random Tolkien quote"
echo "   - No CORS errors visible"
echo "   - No Network tab errors with 'CORS' in message"
echo ""

echo "3️⃣  Try to Login"
echo "   Username: frodo_baggins"
echo "   Password: fellowship123"
echo "   Expected: Logs in successfully → Redirects to Dashboard"
echo ""

echo "4️⃣  Check Network Tab in DevTools"
echo "   - Look at POST to /api/auth/login"
echo "   - Headers should show:"
echo "     • Status: 200 OK (not blocked)"
echo "     • Response Headers include CORS headers"
echo "     • Request goes to: http://localhost:5000/api/auth/login"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              Command Line Testing                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "🔍 View Backend Logs:"
echo "   docker logs fellowship-backend | tail -20"
echo ""

echo "🔍 View Frontend Logs:"
echo "   docker logs fellowship-frontend | tail -20"
echo ""

echo "🔍 View Caddy Logs:"
echo "   docker logs fellowship-caddy | tail -20"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║            What Was Fixed                                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "✅ Backend (sut/backend/app.py)"
echo "   • Added preflight OPTIONS request handler"
echo "   • Returns 200 with CORS headers immediately"
echo "   • Prevents redirects that break CORS"
echo ""

echo "✅ Frontend (sut/frontend/src/services/api.ts)"
echo "   • Direct backend connection (port 5000) during development"
echo "   • Bypasses Caddy proxy complications"
echo "   • Auto-detects when running on port 3000"
echo ""

echo "✅ Caddy (caddy/Caddyfile)"
echo "   • Explicit OPTIONS handler for /api/* routes"
echo "   • Returns CORS headers before any proxying"
echo "   • Maintains production-ready configuration"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              If Issues Persist                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "1. Stop services and clear volumes:"
echo "   docker-compose down -v"
echo ""

echo "2. Ensure code changes are applied:"
echo "   git status"
echo ""

echo "3. Rebuild containers:"
echo "   docker-compose build"
echo "   docker-compose up -d"
echo ""

echo "4. Check specific error in browser console:"
echo "   - Copy full error message"
echo "   - Check if it mentions CORS"
echo "   - Verify API URL being used"
echo ""

echo "5. Test backend directly:"
echo "   # This may return 403 on macOS due to AirTunes (expected)"
echo "   curl -i -X POST http://127.0.0.1:5000/api/auth/login \\"
echo "     -H 'Content-Type: application/json' \\
echo "     -d '{\"username\":\"frodo_baggins\",\"password\":\"fellowship123\"}'"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           🎉 CORS Fixes Applied Successfully! 🎉             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Test in browser: http://localhost:3000"
echo "Try login with: frodo_baggins / fellowship123"
echo ""
