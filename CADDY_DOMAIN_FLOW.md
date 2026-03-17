# CADDY_DOMAIN Flow Analysis

## Current Architecture

### 1. Lambda Function Creates Domain (classroom_instance_manager.py)
```python
# Lines 1024-1034: Domain is injected into user_data as environment variables
domain_exports = f"""# Domain information injected by Lambda (available immediately)
export CADDY_DOMAIN={domain}
export MACHINE_NAME={machine_name}
export WORKSHOP_NAME={workshop_name}
"""

# Lines 1073-1091: Passed to EC2 instance
response = ec2.run_instances(
    ...
    UserData=user_data,  # Contains CADDY_DOMAIN export
    ...
)

# Lines 1015-1017: Also sets EC2 tags
tags.append({'Key': 'HttpsDomain', 'Value': domain})
tags.append({'Key': 'HttpsUrl', 'Value': https_url})
tags.append({'Key': 'HttpsEnabled', 'Value': 'true'})
```

**Domain Name Format**: `{machine_name}.{workshop_name}.{HTTPS_BASE_DOMAIN}`
Example: `fellowship-tut2-pool-0.fellowship.testingfantasy.com`


### 2. User Data Script Receives Domain (user_data.sh)
```bash
# Lines 54-56: Export CADDY_DOMAIN if provided
if [ -n "$CADDY_DOMAIN" ]; then
    export CADDY_DOMAIN
    log "Domain from user_data: $CADDY_DOMAIN"
fi

# Calls setup_fellowship.sh which inherits the export
exec "$SETUP_SCRIPT"
```


### 3. Setup Script Uses Domain (setup_fellowship.sh)
```bash
# Lines 127-128: Check if CADDY_DOMAIN was inherited from user_data
if [ -n "$CADDY_DOMAIN" ] && [ "$CADDY_DOMAIN" != "" ]; then
    log "✓ Found Caddy domain from user_data environment: $CADDY_DOMAIN"

# Lines 186-189: Attempts to pass to docker-compose
log "Starting SUT containers with CADDY_DOMAIN=${CADDY_DOMAIN}..."
export CADDY_DOMAIN
DEPLOY_OUTPUT=$(su - ec2-user -c "cd ~/fellowship-sut && CADDY_DOMAIN='${CADDY_DOMAIN}' docker compose up -d 2>&1")
```

**PROBLEM**: `su - ec2-user` with `-` flag creates a login shell that doesn't properly inherit environment variables passed inline.


### 4. Docker-Compose Config (docker-compose.yml)
```yaml
caddy:
  image: caddy:2-alpine
  ...
  environment:
    - CADDY_DOMAIN=${CADDY_DOMAIN}   # <- Expects CADDY_DOMAIN from shell/environment
```

**PROBLEM**: The environment variable isn't being resolved because docker-compose reads from:
1. `CADDY_DOMAIN` environment variable (NOT being passed correctly through `su -`)
2. `.env` file in the working directory (DOESN'T EXIST)
3. Shell environment (NOT inherited through `su -` properly)


## Why It Fails

1. Lambda injects `export CADDY_DOMAIN=fellowship-tut2-pool-0.fellowship.testingfantasy.com` into user_data ✓
2. setup_fellowship.sh receives it and exports it ✓
3. BUT: `su - ec2-user -c "cd ~/fellowship-sut && CADDY_DOMAIN='...' docker compose up -d"` doesn't work because:
   - `su - ec2-user` creates a login shell (cleans environment)
   - The inline `CADDY_DOMAIN='...'` is not properly evaluated before the -c command
   - docker-compose then looks for CADDY_DOMAIN in:
     - The running environment (empty - the login shell doesn't have it)
     - A `.env` file (doesn't exist)
     - shell variable expansions in docker-compose.yml (fails because ${CADDY_DOMAIN} is empty)

**Result**: Caddy defaults to `localhost` instead of the actual domain


## Solution Options

### Option 1: Create .env File (RECOMMENDED)
```bash
# In setup_fellowship.sh, after getting CADDY_DOMAIN:
mkdir -p /home/ec2-user/fellowship-sut
echo "CADDY_DOMAIN=${CADDY_DOMAIN}" > /home/ec2-user/fellowship-sut/.env
chown ec2-user:ec2-user /home/ec2-user/fellowship-sut/.env

# docker-compose automatically reads .env file
su - ec2-user -c "cd ~/fellowship-sut && docker compose up -d"
```

### Option 2: Modify docker-compose.yml
```yaml
caddy:
  environment:
    CADDY_DOMAIN: ${CADDY_DOMAIN:-localhost}  # Add default value
```

### Option 3: Pass via Command Line
```bash
su - ec2-user -c "cd ~/fellowship-sut && docker compose --env-file <(echo 'CADDY_DOMAIN=${CADDY_DOMAIN}') up -d"
```

### Option 4: Source .bashrc Modification
```bash
# Modify /home/ec2-user/.bashrc to read CADDY_DOMAIN from a file
echo "export CADDY_DOMAIN=\$(cat /etc/caddy-domain 2>/dev/null)" >> /home/ec2-user/.bashrc
chown ec2-user:ec2-user /home/ec2-user/.bashrc

# Write domain to file
echo "${CADDY_DOMAIN}" > /etc/caddy-domain
```

## Recommended Implementation

**Option 1 is cleanest and most reliable**:

1. **In setup_fellowship.sh** - Create .env file instead of relying on environment variable inheritance
2. **In docker-compose.yml** - Add default value as fallback
3. **In setup_fellowship.sh** - After docker-compose up, verify port 80 is responding with the correct domain

## Files to Modify

1. **setup_fellowship.sh** (Lines 185-200)
   - After line 182 (CADDY_DOMAIN check), add:
   ```bash
   # Create .env file for docker-compose
   cat > /home/ec2-user/fellowship-sut/.env << EOF
   CADDY_DOMAIN=${CADDY_DOMAIN}
   EOF
   chown ec2-user:ec2-user /home/ec2-user/fellowship-sut/.env
   ```
   - Simplify line 189 to just: `su - ec2-user -c "cd ~/fellowship-sut && docker compose up -d 2>&1"`

2. **docker-compose.yml** (Line 58)
   - Add default value: `- CADDY_DOMAIN=${CADDY_DOMAIN:-localhost}`

3. **setup_fellowship.sh** (After containers start)
   - Add health check to verify Caddy is using correct domain:
   ```bash
   # Test local connectivity with domain
   if curl -s -H "Host: ${CADDY_DOMAIN}" http://localhost/api/health >/dev/null 2>&1; then
       log "✓ Caddy is responding with domain: ${CADDY_DOMAIN}"
   else
       log "WARNING: Caddy may not be configured with domain: ${CADDY_DOMAIN}"
   fi
   ```
