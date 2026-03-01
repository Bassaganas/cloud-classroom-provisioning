# CORS Issue Resolution Guide for Fellowship SUT Local Development

## Problem Description

**Error**: `Access to XMLHttpRequest at 'http://localhost/api/auth/login' from origin 'http://localhost:3000' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: Redirect is not allowed for a preflight request.`

**Root Cause**: Browser CORS preflight `OPTIONS` requests were being redirected before CORS headers could be applied. CORS policy forbids redirects on preflight requests.

---

## What Was Fixed

### 1. **Backend CORS Configuration** (`sut/backend/app.py`)

**Changes Made:**
- Added `request` import from Flask
- Moved CORS initialization earlier in app setup
- Added explicit `before_request` handler to catch OPTIONS preflight requests
- Handler returns immediate 200 response with proper CORS headers before any redirects

```python
@app.before_request
def handle_preflight():
    '''Handle CORS preflight requests immediately before any redirects'''
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        response.headers.add('Access-Control-Max-Age', '3600')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200
```

**Why This Works**: 
- Catches preflight requests early before any redirect logic
- Returns 200 OK immediately with CORS headers
- Prevents Caddy or other proxies from interfering

### 2. **Frontend API Service** (`sut/frontend/src/services/api.ts`)

**Changes Made:**
- Modified `getApiUrl()` to connect directly to backend on port 5000 when accessing via port 3000
- Replaced: `http://localhost/api` (through Caddy proxy)
- With: `http://localhost:5000/api` (direct backend connection)
- Added timeout configuration (10 seconds)
- Added error interceptor for better debugging

```typescript
// OLD: Uses Caddy proxy (causes redirect issues)
return `${window.location.protocol}//${window.location.hostname}/api`;

// NEW: Connects directly to backend (bypasses Caddy)
return 'http://localhost:5000/api';
```

**Why This Works**:
- Bypasses Caddy proxy during development
- Avoids redirect complications
- Direct connection to backend CORS handler
- Still allows Caddy for production use via relative paths

### 3. **Caddy Configuration** (`caddy/Caddyfile`)

**Changes Made:**
- Added explicit handling for OPTIONS preflight requests
- Returns 200 with CORS headers immediately for `/api/*` routes
- Prevents Caddy from processing redirects on preflight requests
- Enhanced reverse proxy with proper forwarded headers

```caddy
handle /api/* {
    @options {
        method OPTIONS
    }
    
    # Return 200 OK for preflight OPTIONS requests immediately
    route @options {
        header Access-Control-Allow-Origin "*"
        header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        header Access-Control-Allow-Headers "Content-Type, Authorization, Accept"
        header Access-Control-Max-Age "3600"
        respond 200
    }
    
    # For actual requests, proxy to backend
    reverse_proxy backend:5000 {
        header_upstream Host {http.request.host}
        header_upstream X-Real-IP {client_ip}
        header_upstream X-Forwarded-For {client_ip}
        header_upstream X-Forwarded-Proto {http.request.proto}
    }
}
```

**Why This Works**:
- Handles OPTIONS requests at Caddy level
- Prevents any redirect processing for preflight requests
- Provides proper forwarded headers for backend

---

## How to Apply Fixes

### Option 1: Quick Fix (Recommended for Development)

```bash
cd iac/aws/workshops/fellowship/fellowship-sut

# Stop existing containers
docker-compose down

# Rebuild with new configurations
docker-compose build --no-cache backend frontend

# Start services
docker-compose up -d

# Wait for services to be ready
sleep 15

# Access the app
open http://localhost:3000
```

### Option 2: Using Test Script

```bash
cd iac/aws/workshops/fellowship/fellowship-sut
chmod +x test-cors.sh
./test-cors.sh
```

---

## Verification Steps

### 1. **Check Services Are Running**
```bash
docker ps | grep fellowship
```

Expected output:
```
fellowship-backend   ...  Up
fellowship-frontend  ...  Up
fellowship-caddy     ...  Up
```

### 2. **Test Backend Health**
```bash
curl -i http://localhost:5000/api/health
```

Expected response: `200 OK`

### 3. **Test Preflight Request**
```bash
curl -i -X OPTIONS http://localhost:5000/api/auth/login \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST"
```

Expected response headers:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type,Authorization
```

### 4. **Check Browser Console**
Open http://localhost:3000 and:
1. Open DevTools (F12)
2. Go to Console tab
3. Check for CORS errors (should be gone!)
4. Try login - should work now

### 5. **Test Login**
```bash
# Through direct backend
curl -i -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"frodo_baggins","password":"fellowship123"}'

# Expected: 200 OK with login response
```

---

## Architecture After Fixes

```
┌─────────────────────────────────────────────────────────────┐
│                      Local Development                      │
└─────────────────────────────────────────────────────────────┘

Frontend (port 3000)
    ↓
    ├─→ Direct Backend Connection (port 5000) ✅ [DEVELOPMENT]
    │
    └─→ Caddy Proxy (port 80/443) [PRODUCTION]
            ↓
            └─→ Backend (port 5000)


Request Flow:
1. Frontend makes POST to http://localhost:5000/api/auth/login
2. Browser sends OPTIONS preflight first
3. Backend @before_request handler catches OPTIONS
4. Returns 200 with CORS headers immediately
5. No redirects → No CORS errors ✅
6. Actual POST request proceeds
7. Login succeeds
```

---

## Environment Variables

### docker-compose.yml (Frontend)
```yaml
environment:
  - REACT_APP_API_URL=/api
  - CHOKIDAR_USEPOLLING=true
```

The frontend auto-detects when running on port 3000 and connects directly to backend.

### Backend
No special environment variables needed. Backend handles CORS automatically.

---

## Troubleshooting

### Still Getting CORS Errors?

**1. Clear Docker cache and rebuild**
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
sleep 15
```

**2. Check backend logs for errors**
```bash
docker logs fellowship-backend
```

**3. Check frontend logs**
```bash
docker logs fellowship-frontend
# Look for API URL being used
```

**4. Verify Caddy is running (if accessing via port 80)**
```bash
docker logs fellowship-caddy
```

**5. Test with curl directly**
```bash
# Test OPTIONS
curl -v -X OPTIONS http://localhost:5000/api/auth/login

# Test POST
curl -v -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"frodo_baggins","password":"fellowship123"}'
```

### Port Already in Use?

```bash
# Find what's using the port
lsof -i :3000  # Frontend
lsof -i :5000  # Backend
lsof -i :80    # Caddy

# Kill it
kill -9 <PID>

# Or stop Docker
docker-compose down
```

### Browser Still Caching Old Version?

```bash
# Clear browser cache
# Or use Incognito/Private window
# Or hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
```

---

## Production Deployment

In production deployment (AWS):

1. **Frontend** serves via CloudFront/CDN
2. **All requests** go through Caddy reverse proxy (port 80/443)
3. **Caddy** now properly handles CORS preflight requests
4. **API URL** uses relative path `/api` (Caddy routes to backend)

No changes needed for production - Caddy configuration handles it automatically!

---

## Key Takeaways

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| CORS preflight blocked | Caddy was redirecting OPTIONS requests | Added explicit OPTIONS handler before redirects |
| Redirect not allowed on preflight | Browser CORS policy forbids preflight redirects | Return 200 immediately for OPTIONS with CORS headers |
| Preflight failing | Headers set after redirect logic | Execute CORS handler in `@before_request` hook |

---

## References

- [MDN: CORS Preflight Requests](https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request)
- [Caddy Headers Directive](https://caddyserver.com/docs/caddyfile/directives/header)
- [Flask-CORS Documentation](https://flask-cors.readthedocs.io/)

---

## Files Modified

1. ✅ `sut/backend/app.py` - Added preflight handler
2. ✅ `sut/frontend/src/services/api.ts` - Direct backend connection for dev
3. ✅ `caddy/Caddyfile` - Explicit CORS preflight handling

**All changes are backward compatible and maintain production functionality.**
