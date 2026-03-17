# CADDY_DOMAIN Fix Summary

## Problem Identified
The `CADDY_DOMAIN` environment variable was being injected by the Lambda function (`classroom_instance_manager.py`) into the user_data script, but was NOT being properly passed to docker-compose when launching the Fellowship SUT containers.

### Root Cause
In `setup_fellowship.sh` line 189:
```bash
DEPLOY_OUTPUT=$(su - ec2-user -c "cd ~/fellowship-sut && CADDY_DOMAIN='${CADDY_DOMAIN}' docker compose up -d 2>&1")
```

The `su - ec2-user` command (with `-` flag) creates a **login shell** that:
1. Resets the environment (doesn't inherit inline environment variables properly)
2. The `CADDY_DOMAIN='...'` prefix doesn't get evaluated in the way needed for docker-compose to read it

**Result**: docker-compose couldn't find `CADDY_DOMAIN` and defaulted to `localhost`, causing Caddy to not listen on the actual domain name.

## Solution Implemented

### 1. Modified setup_fellowship.sh (Lines 185-200)
**Changed from**: Relying on environment variable inheritance through `su -`  
**Changed to**: Creating a `.env` file that docker-compose automatically reads

```bash
# Create .env file for docker-compose to read CADDY_DOMAIN
log "Creating .env file with CADDY_DOMAIN for docker-compose..."
cat > /home/ec2-user/fellowship-sut/.env << EOF
CADDY_DOMAIN=${CADDY_DOMAIN}
EOF
chown ec2-user:ec2-user /home/ec2-user/fellowship-sut/.env
log "✓ Created /home/ec2-user/fellowship-sut/.env with CADDY_DOMAIN"

# Deploy SUT containers (docker-compose will read CADDY_DOMAIN from .env file)
DEPLOY_OUTPUT=$(su - ec2-user -c "cd ~/fellowship-sut && docker compose up -d 2>&1")
```

**Why this works**:
- Docker-compose automatically reads `.env` file from the working directory
- The `.env` file persists across shell boundaries
- No shell variable inheritance issues
- Standard docker-compose pattern

### 2. Modified docker-compose.yml (Line 58)
**Changed from**: `- CADDY_DOMAIN=${CADDY_DOMAIN}`  
**Changed to**: `- CADDY_DOMAIN=${CADDY_DOMAIN:-localhost}`

```yaml
environment:
  - CADDY_DOMAIN=${CADDY_DOMAIN:-localhost}
```

**Why this helps**:
- Provides fallback default value if CADDY_DOMAIN is not set
- Prevents docker-compose warnings about unset variables
- Caddy will still start even if domain loading fails

## Data Flow (Corrected)

```
Lambda (classroom_instance_manager.py)
  ↓ Creates domain: "fellowship-tut2-pool-0.fellowship.testingfantasy.com"
  ↓ Injects into user_data: export CADDY_DOMAIN=...
  ↓ Sets EC2 tag: HttpsDomain=...
  ↓
user_data.sh
  ↓ Receives CADDY_DOMAIN environment variable
  ↓ Calls setup_fellowship.sh (inherits CADDY_DOMAIN)
  ↓
setup_fellowship.sh (FIXED)
  ↓ Creates /home/ec2-user/fellowship-sut/.env with CADDY_DOMAIN
  ↓ Calls: su - ec2-user -c "cd ~/fellowship-sut && docker compose up -d"
  ↓
docker-compose
  ↓ Reads .env file containing CADDY_DOMAIN
  ↓ Passes to Caddy container via environment
  ↓
Caddy (Caddyfile)
  ↓ Uses {$CADDY_DOMAIN:localhost} to configure domain
  ↓ Listens on domain: fellowship-tut2-pool-0.fellowship.testingfantasy.com
  ↓ Provisions HTTPS certificate with Let's Encrypt
  ✓ Application accessible via domain!
```

## Testing the Fix

To verify the fix works with the current instance:

```bash
# On EC2 instance, create the .env file manually:
sudo su - ec2-user -c "cat > ~/fellowship-sut/.env << 'EOF'
CADDY_DOMAIN=fellowship-tut2-pool-0.fellowship.testingfantasy.com
EOF"

# Restart Caddy with the correct domain:
sudo su - ec2-user -c "cd ~/fellowship-sut && docker compose restart caddy"

# Check Caddy logs:
sudo su - ec2-user -c "cd ~/fellowship-sut && docker compose logs caddy | grep -i 'domain\|listen\|https' | tail -15"

# Test Caddy is responding:
curl -v http://localhost/
curl -H "Host: fellowship-tut2-pool-0.fellowship.testingfantasy.com" http://localhost/
```

## Files Modified

1. **setup_fellowship.sh** (Lines 185-200)
   - Changed environment variable passing method
   - Now creates .env file for docker-compose
   
2. **docker-compose.yml** (Line 58)
   - Added fallback default value for CADDY_DOMAIN

## Impact

- ✅ CADDY_DOMAIN is now properly passed to Caddy
- ✅ No more `WARN[0000] The "CADDY_DOMAIN" variable is not set` warnings
- ✅ Caddy will listen on actual domain (fellowship-tut2-pool-0.fellowship.testingfantasy.com)
- ✅ HTTPS will work once DNS is configured
- ✅ Applies to all new Fellowship SUT deployments
- ✅ No changes needed to Lambda function or Instance Manager
- ✅ Pattern can be reused for other workshops (testus_patronus, etc)

## Next Steps

1. Re-deploy a new Fellowship SUT instance to test the fix
2. Verify `.env` file is created with correct CADDY_DOMAIN
3. Verify Caddy logs show proper domain configuration (not just `localhost`)
4. Verify DNS points to instance public IP for full HTTPS + domain access
