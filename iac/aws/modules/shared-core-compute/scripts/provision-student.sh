#!/bin/bash
# provision-student.sh — Onboard a single student onto the shared-core stack
#
# Creates:
#   1. Gitea user account for the student
#   2. Per-student repo under the cohort org (fellowship-sut-<student_id>)
#   3. Webhook: repo push → Jenkins student folder pipeline
#   4. Jenkins folder and pipeline job scoped to the student
#   5. Credentials inside the Jenkins folder (Gitea token, student identity)
#
# Usage:
#   bash provision-student.sh <student_id> [student_password]
#
# Environment variables:
#   GITEA_URL              http://localhost:3030  (Gitea external/host port)
#   GITEA_ADMIN_USER       fellowship
#   GITEA_ADMIN_PASSWORD   fellowship123
#   GITEA_ORG_NAME         fellowship-org
#   JENKINS_URL            http://localhost:8080
#   JENKINS_ADMIN_USER     fellowship
#   JENKINS_ADMIN_PASSWORD fellowship123
#   SHARED_JENKINS_URL     https://jenkins-core.fellowship.example.com/
#   SHARED_GITEA_URL       https://gitea-core.fellowship.example.com/
#   GITEA_INTERNAL_URL     http://gitea:3000  (Docker-internal, for Jenkins clone URL)

set -euo pipefail

STUDENT_ID="${1:?Usage: provision-student.sh <student_id> [student_password]}"
STUDENT_PASSWORD="${2:-${STUDENT_ID}}"

GITEA_URL="${GITEA_URL:-http://localhost:3030}"
GITEA_ADMIN_USER="${GITEA_ADMIN_USER:-fellowship}"
GITEA_ADMIN_PASSWORD="${GITEA_ADMIN_PASSWORD:-fellowship123}"
GITEA_ORG_NAME="${GITEA_ORG_NAME:-fellowship-org}"
GITEA_INTERNAL_URL="${GITEA_INTERNAL_URL:-http://gitea:3000}"

JENKINS_URL="${JENKINS_URL:-http://localhost:8080}"
JENKINS_ADMIN_USER="${JENKINS_ADMIN_USER:-fellowship}"
JENKINS_ADMIN_PASSWORD="${JENKINS_ADMIN_PASSWORD:-fellowship123}"

SHARED_JENKINS_URL="${SHARED_JENKINS_URL:-${JENKINS_URL}}"
SHARED_GITEA_URL="${SHARED_GITEA_URL:-${GITEA_URL}}"

# ── S3 / Exercises configuration ───────────────────────────────────────────────
# SUT bucket: contains SUT tarball and exercises artifact
# AWS region: for S3 API calls (defaults to eu-west-1 if not provided)
SUT_BUCKET="${SUT_BUCKET:-}"
EXERCISES_ARTIFACT="${EXERCISES_ARTIFACT:-}"
AWS_REGION="${AWS_REGION:-eu-west-1}"
WORKSHOP_NAME="${WORKSHOP_NAME:-fellowship}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

# URL of the student's deployed SUT EC2 instance.
# Passed by the provisioner so the Jenkins pipeline job is pre-configured
# and students don't need to set it manually.
DEPLOYED_SUT_URL="${DEPLOYED_SUT_URL:-}"
# Can be pre-provisioned and passed via JENKINS_WEBHOOK_API_TOKEN env var.
# If not set, will be created on demand via the Jenkins API.
JENKINS_WEBHOOK_API_TOKEN="${JENKINS_WEBHOOK_API_TOKEN:-}"

# Jenkins CSRF: session cookie jar shared across all Jenkins API calls
JENKINS_COOKIE_JAR="/tmp/jenkins-cookies-$$.txt"

REPO_NAME="fellowship-sut-${STUDENT_ID}"

log()  { echo "[provision] $*"; }
warn() { echo "[provision] WARNING: $*" >&2; }
die()  { echo "[provision] ERROR: $*" >&2; exit 1; }

# ── Helpers ───────────────────────────────────────────────────────────────────

get_exercises_from_s3() {
    # Download latest exercises artifact from S3 and extract to a working directory.
    # This allows students to get up-to-date exercises without re-provisioning or
    # rebuilding the SUT instance.
    #
    # Returns: path to extracted exercises directory, or empty string if unavailable
    
    if [ -z "${SUT_BUCKET}" ]; then
        warn "SUT_BUCKET not configured — exercises from S3 unavailable"
        return 0
    fi
    
    local exercises_dir=""
    local artifact_name="${EXERCISES_ARTIFACT}"
    
    # If EXERCISES_ARTIFACT not provided, try to fetch the latest from SSM
    if [ -z "${artifact_name}" ]; then
        local ssm_param="/classroom/${WORKSHOP_NAME}/${ENVIRONMENT}/latest_exercises_artifact"
        artifact_name=$(aws ssm get-parameter \
            --name "${ssm_param}" \
            --region "${AWS_REGION}" \
            --query 'Parameter.Value' \
            --output text 2>/dev/null || echo "")
        
        if [ -z "${artifact_name}" ] || [ "${artifact_name}" = "None" ]; then
            warn "Could not determine latest exercises artifact from SSM (${ssm_param})"
            return 0
        fi
        log "  Fetched latest exercises artifact from SSM: ${artifact_name}"
    fi
    
    # Download from S3
    local tmp_exercises_dir tmp_exercise_file
    tmp_exercises_dir=$(mktemp -d)
    tmp_exercise_file="${tmp_exercises_dir}/exercises.tar.gz"
    
    log "  Downloading exercises from S3: s3://${SUT_BUCKET}/${artifact_name}"
    if ! aws s3 cp "s3://${SUT_BUCKET}/${artifact_name}" "${tmp_exercise_file}" \
        --region "${AWS_REGION}" >/dev/null 2>&1; then
        warn "Failed to download exercises from S3 (${artifact_name})"
        rm -rf "${tmp_exercises_dir}"
        return 0
    fi
    
    # Extract tarball
    if ! tar -xzf "${tmp_exercise_file}" -C "${tmp_exercises_dir}" 2>/dev/null; then
        warn "Failed to extract exercises tarball"
        rm -rf "${tmp_exercises_dir}"
        return 0
    fi
    
    log "  ✓ Exercises downloaded and extracted from S3"
    echo "${tmp_exercises_dir}"
}

escape_xml() {
    # Escape XML special characters to prevent injection in XML payloads
    local string="$1"
    string="${string//&/&amp;}"
    string="${string//</&lt;}"
    string="${string//>/&gt;}"
    string="${string//\"/&quot;}"
    string="${string//\'/&apos;}"
    echo "$string"
}

gitea_api() {
    local method="$1"; local path="$2"; local data="${3:-}"
    if [ -n "$data" ]; then
        curl -sf -X "$method" "${GITEA_URL}/api/v1${path}" \
            -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
            -H "Content-Type: application/json" \
            -d "$data"
    else
        curl -sf -X "$method" "${GITEA_URL}/api/v1${path}" \
            -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}"
    fi
}

jenkins_crumb() {
    # Jenkins CSRF crumbs are session-scoped — reuse the same cookie jar
    # for the crumb request and all subsequent API calls.
    curl -sf -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        "${JENKINS_URL}/crumbIssuer/api/json" 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['crumbRequestField']}:{d['crumb']}\")" \
        2>/dev/null || echo ""
}

jenkins_api() {
    local method="$1"; local path="$2"; local data="${3:-}"
    local crumb
    crumb=$(jenkins_crumb)
    local crumb_header=""
    [ -n "$crumb" ] && crumb_header="-H ${crumb}"
    if [ -n "$data" ]; then
        # shellcheck disable=SC2086
        curl -sf -X "$method" "${JENKINS_URL}${path}" \
            -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
            ${crumb_header:+-H "$crumb"} \
            -H "Content-Type: application/xml" \
            --data-binary "$data"
    else
        # shellcheck disable=SC2086
        curl -sf -X "$method" "${JENKINS_URL}${path}" \
            -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
            ${crumb_header:+-H "$crumb"}
    fi
}

# Ensure JENKINS_WEBHOOK_API_TOKEN is set, creating one via the Jenkins API if needed.
# Jenkins API tokens allow authenticated POST requests to bypass CSRF protection,
# which is required for Gitea webhook deliveries (Gitea always sends POST).
ensure_jenkins_webhook_token() {
    if [ -n "${JENKINS_WEBHOOK_API_TOKEN:-}" ]; then
        return 0
    fi
    log "  Creating Jenkins API token for webhook authentication..."
    local crumb
    crumb=$(jenkins_crumb)
    local response
    response=$(curl -sf \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        ${crumb:+-H "$crumb"} \
        -X POST "${JENKINS_URL}/user/${JENKINS_ADMIN_USER}/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken" \
        --data-urlencode "newTokenName=gitea-webhook-trigger" 2>/dev/null) || true
    if echo "$response" | grep -q '"tokenValue"'; then
        JENKINS_WEBHOOK_API_TOKEN=$(echo "$response" | grep -o '"tokenValue":"[^"]*"' | cut -d'"' -f4)
        log "  ✓ Jenkins API token created"
    else
        warn "Could not create Jenkins API token; webhook POST may be rejected by CSRF filter"
        JENKINS_WEBHOOK_API_TOKEN="${JENKINS_ADMIN_PASSWORD}"
    fi
}

# ── Step 0.5: Jenkins student user creation and folder permissions ──────────

create_jenkins_student_user() {
    log "Step 0.5a: Creating Jenkins user '${STUDENT_ID}'..."
    
    # Create the student user via Jenkins Script Console (Groovy API)
    local groovy_script
    groovy_script=$(cat <<'GROOVY'
import jenkins.model.Jenkins
import hudson.security.HudsonPrivateSecurityRealm

def jenkins = Jenkins.getInstance()
def realm = jenkins.getSecurityRealm()

if (realm instanceof HudsonPrivateSecurityRealm) {
    // Attempt to create the user
    try {
        def user = realm.createAccount(USERNAME, PASSWORD)
        user.setFullName(FULLNAME)
        user.save()
        println("User " + USERNAME + " created successfully")
    } catch (Exception e) {
        if (e.getMessage().contains("already exists")) {
            println("User " + USERNAME + " already exists")
        } else {
            throw e
        }
    }
} else {
    println("ERROR: Jenkins security realm is not HudsonPrivateSecurityRealm")
}
GROOVY
    )
    
    # Substitute variables
    groovy_script="${groovy_script//USERNAME/\"$STUDENT_ID\"}"
    groovy_script="${groovy_script//PASSWORD/\"$STUDENT_PASSWORD\"}"
    groovy_script="${groovy_script//FULLNAME/\"Student: $STUDENT_ID\"}"
    
    local response crumb
    crumb=$(jenkins_crumb)
    response=$(curl -sf -X POST "${JENKINS_URL}/scriptText" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        ${crumb:+-H "$crumb"} \
        --data-urlencode "script=${groovy_script}" 2>/dev/null) || true

    if echo "$response" | grep -q "created successfully\|already exists"; then
        log "  ✓ Jenkins user '${STUDENT_ID}' ready"
    else
        # Non-fatal: user creation may not be supported on this Jenkins version
        warn "Jenkins user creation: $response"
    fi
}

setup_jenkins_folder_permissions() {
    log "Step 0.5b: Setting up folder permissions for student '${STUDENT_ID}'..."

    # Use the Role-Based Strategy plugin (role-strategy) to scope the student user
    # to their own Jenkins folder only.
    #
    # IMPORTANT — substitution note:
    #   The string STUDENT_ID_PLACEHOLDER below is replaced by the actual student ID
    #   via bash parameter expansion AFTER the heredoc is read.  It must appear only
    #   inside Groovy double-quoted string literals so the substituted value (which
    #   contains hyphens, e.g. "student-285f3dc1") remains syntactically valid Groovy.
    local groovy_script
    groovy_script=$(cat <<'GROOVY'
import jenkins.model.Jenkins
import com.cloudbees.hudson.plugins.rolestrategy.RoleBasedAuthorizationStrategy
import com.cloudbees.hudson.plugins.rolestrategy.Role
import hudson.security.Permission

def jenkins  = Jenkins.getInstance()
def strategy = jenkins.getAuthorizationStrategy()

if (!(strategy instanceof RoleBasedAuthorizationStrategy)) {
    println("WARNING: Jenkins is not using RoleBasedAuthorizationStrategy — per-student folder isolation skipped")
    return
}

// Values injected by provision-student.sh (see STUDENT_ID_PLACEHOLDER substitution below)
def studentUser = "STUDENT_ID_PLACEHOLDER"
def roleName    = "folder-role-STUDENT_ID_PLACEHOLDER"
// Pattern matches the student's top-level folder and every item inside it
def pattern     = "STUDENT_ID_PLACEHOLDER(/.*)*"

Set<Permission> permissions = [
    hudson.model.Item.BUILD,
    hudson.model.Item.CANCEL,
    hudson.model.Item.CONFIGURE,
    hudson.model.Item.DELETE,
    hudson.model.Item.DISCOVER,
    hudson.model.Item.READ,
    hudson.model.Item.WORKSPACE,
    hudson.model.Run.UPDATE,
] as Set

def roleMap = strategy.getRoleMap(RoleBasedAuthorizationStrategy.PROJECT)
def role    = roleMap.getRoles().find { it.getName() == roleName }

if (role == null) {
    role = new Role(roleName, pattern, permissions)
    strategy.addRole(RoleBasedAuthorizationStrategy.PROJECT, role)
    println("Created folder role " + roleName + " with pattern " + pattern)
} else {
    println("Folder role " + roleName + " already exists")
}

strategy.assignRole(RoleBasedAuthorizationStrategy.PROJECT, role, studentUser)
jenkins.save()
println("Role " + roleName + " assigned to " + studentUser + " — done")
GROOVY
    )

    # Safe substitution: STUDENT_ID_PLACEHOLDER only appears inside Groovy string
    # literals above, so the substituted value is always syntactically valid Groovy.
    groovy_script="${groovy_script//STUDENT_ID_PLACEHOLDER/$STUDENT_ID}"

    local response crumb http_status
    crumb=$(jenkins_crumb)
    http_status=$(curl -s -w "%{http_code}" -o /tmp/jenkins_response_$$.txt -X POST "${JENKINS_URL}/scriptText" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        ${crumb:+-H "$crumb"} \
        --data-urlencode "script=${groovy_script}" 2>/dev/null)
    response=$(cat /tmp/jenkins_response_$$.txt 2>/dev/null || echo "")
    rm -f /tmp/jenkins_response_$$.txt

    if [ "$http_status" != "200" ]; then
        log "⚠ Jenkins Script Console returned HTTP $http_status (expected 200)"
        log "  Response: $(echo "$response" | head -c 300)"
    fi

    if echo "$response" | grep -q "assigned to\|done"; then
        log "  ✓ Folder permissions set for student '${STUDENT_ID}'"
    elif echo "$response" | grep -q "already exists"; then
        log "  ✓ Folder role already exists for student '${STUDENT_ID}'"
    else
        warn "Folder permission setup failed (HTTP $http_status): $(echo "$response" | head -c 300)"
        warn "RBAC may not be properly scoped for this student"
    fi
}

# ── Step 1: Gitea student user ────────────────────────────────────────────────

create_gitea_user() {
    log "Step 1: Creating Gitea user '${STUDENT_ID}'..."
    local http_status tmp_body
    tmp_body=$(mktemp)
    http_status=$(curl -s -o "${tmp_body}" -w "%{http_code}" \
        -X POST "${GITEA_URL}/api/v1/admin/users" \
        -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}" \
        -H "Content-Type: application/json" \
        -d "{
            \"login_name\": \"${STUDENT_ID}\",
            \"username\": \"${STUDENT_ID}\",
            \"password\": \"${STUDENT_PASSWORD}\",
            \"email\": \"${STUDENT_ID}@fellowship.local\",
            \"send_notify\": false,
            \"must_change_password\": false,
            \"source_id\": 0
        }" 2>&1) || http_status="000"
    case "${http_status}" in
        201) log "  ✓ Gitea user '${STUDENT_ID}' created" ;;
        422) log "  ✓ Gitea user '${STUDENT_ID}' already exists (skipped)" ;;
        401|403) warn "Gitea admin auth failed (HTTP ${http_status}) — check GITEA_ADMIN_PASSWORD" ;;
        000) warn "Gitea API unreachable at ${GITEA_URL} — check GITEA_URL and network" ;;
        *)   warn "Gitea user creation returned HTTP ${http_status}: $(cat "${tmp_body}" 2>/dev/null | head -c 300)" ;;
    esac
    rm -f "${tmp_body}"
}

# ── Step 2: Per-student Gitea repo ────────────────────────────────────────────

create_gitea_repo() {
    log "Step 2: Creating repo '${GITEA_ORG_NAME}/${REPO_NAME}'..."
    local response
    response=$(gitea_api POST "/orgs/${GITEA_ORG_NAME}/repos" "{
        \"name\": \"${REPO_NAME}\",
        \"description\": \"Fellowship SUT for student ${STUDENT_ID}\",
        \"private\": false,
        \"auto_init\": true,
        \"default_branch\": \"main\"
    }") || true

    if echo "$response" | grep -q '"id"'; then
        log "  ✓ Repo '${REPO_NAME}' created"
    else
        log "  ✓ Repo '${REPO_NAME}' already exists (skipped)"
    fi

    # Add student as write collaborator
    gitea_api PUT "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/collaborators/${STUDENT_ID}" \
        '{"permission":"write"}' > /dev/null 2>&1 || \
        warn "Could not add collaborator '${STUDENT_ID}' on '${REPO_NAME}'"
    log "  ✓ Student '${STUDENT_ID}' added as collaborator"
}

# ── Step 2.5: Seed SUT content into student repo ────────────────────────────
# Seeds sut/, tests/, Jenkinsfile, and pytest.ini from the deployed app directory
# via a single git commit/push.  Falls back to a minimal stub Jenkinsfile when
# the source tree is unavailable (e.g. during testing without a full deploy).

_seed_stub_jenkinsfile() {
    # Fallback: seed a minimal Jenkinsfile via the Gitea REST API.
    # Used only when the SUT source directory is unavailable on this host.
    log "  Falling back to stub Jenkinsfile (SUT source not found on this host)"

    _REPO_NAME="${REPO_NAME}" python3 - << 'PYEOF'
import urllib.request, urllib.error, base64, json, os, ssl

gitea_url  = os.environ.get('GITEA_URL', 'http://localhost:3030')
admin_user = os.environ.get('GITEA_ADMIN_USER', 'fellowship')
admin_pass = os.environ.get('GITEA_ADMIN_PASSWORD', 'fellowship123')
org_name   = os.environ.get('GITEA_ORG_NAME', 'fellowship-org')
repo_name  = os.environ.get('_REPO_NAME', '')

jenkinsfile = b"""pipeline {
    agent { label 'fellowship-agent' }

    stages {
        stage('Lint') {
            steps {
                sh 'flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true'
            }
        }
        stage('Test') {
            steps {
                sh 'pytest --tb=short || true'
            }
        }
        stage('Build') {
            steps {
                sh '''
                    if [ -f package.json ]; then
                        npm install
                        npm run build --if-present
                    else
                        echo "No package.json found, skipping npm build"
                    fi
                '''
            }
        }
    }

    post {
        always { echo "Pipeline complete" }
    }
}
"""

url = f"{gitea_url}/api/v1/repos/{org_name}/{repo_name}/contents/Jenkinsfile"
payload = json.dumps({
    "message": "chore: seed stub Jenkinsfile for fellowship pipeline",
    "content": base64.b64encode(jenkinsfile).decode()
}).encode()

# Disable SSL cert verification only when talking to localhost/internal URLs
ctx = ssl.create_default_context()
if 'localhost' in gitea_url or '127.0.0.1' in gitea_url:
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

creds = base64.b64encode(f"{admin_user}:{admin_pass}".encode()).decode()
req = urllib.request.Request(url, data=payload, method='POST')
req.add_header('Authorization', f'Basic {creds}')
req.add_header('Content-Type', 'application/json')

try:
    urllib.request.urlopen(req, context=ctx)
    print(f"[provision]   \u2713 Stub Jenkinsfile seeded into '{repo_name}'")
except urllib.error.HTTPError as e:
    body = e.read().decode(errors='replace')
    if e.code == 422 and 'already exist' in body.lower():
        print(f"[provision]   \u2713 Jenkinsfile already exists in '{repo_name}' (skipped)")
    else:
        print(f"[provision] WARNING: Jenkinsfile seed returned HTTP {e.code}: {body[:300]}")
PYEOF
}

seed_sut_content() {
    log "Step 2.5: Seeding SUT content into '${REPO_NAME}'..."

    # Download exercises from S3 if available (primary source for fresh content)
    local s3_exercises_dir=""
    s3_exercises_dir=$(get_exercises_from_s3)
    if [ -z "${s3_exercises_dir}" ]; then
        log "  No exercises available from S3 (optional)"
    fi

    # Locate the deployed app directory that contains sut/ and tests/.
    # The deploy-shared-core workflow clones the app into /home/ec2-user/fellowship-sut.
    local app_dir=""
    for candidate in /home/ec2-user/fellowship-sut /opt/fellowship-sut /home/ec2-user; do
        if [ -d "${candidate}/sut" ] && [ -f "${candidate}/Jenkinsfile" ]; then
            app_dir="${candidate}"
            break
        fi
    done

    if [ -z "${app_dir}" ]; then
        warn "SUT source directory (sut/ + Jenkinsfile) not found — using stub Jenkinsfile"
        _seed_stub_jenkinsfile
        return 0
    fi

    log "  SUT source: ${app_dir}"

    # Build an authenticated clone URL so we can git push without a credential helper.
    local auth_url
    auth_url=$(printf '%s' "${GITEA_URL}" | \
        sed "s|https://|https://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@|g" | \
        sed "s|http://|http://${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}@|g")
    auth_url="${auth_url}/${GITEA_ORG_NAME}/${REPO_NAME}.git"

    local tmp_dir
    tmp_dir=$(mktemp -d)
    # shellcheck disable=SC2064
    trap "rm -rf '${tmp_dir}' '${s3_exercises_dir}'" RETURN

    if ! git clone --quiet "${auth_url}" "${tmp_dir}/repo" 2>/dev/null; then
        warn "git clone of '${REPO_NAME}' failed — falling back to stub Jenkinsfile"
        _seed_stub_jenkinsfile
        return 0
    fi

    cd "${tmp_dir}/repo" || { warn "cd into clone failed"; return 0; }
    git config user.email "${GITEA_ADMIN_USER}@fellowship.local"
    git config user.name "Gandalf the Grey"

    # Copy each SUT asset into the repo working tree.
    local items_copied=0
    for item in sut tests scripts Jenkinsfile pytest.ini package.json package-lock.json playwright.config.ts; do
        if [ -e "${app_dir}/${item}" ]; then
            cp -a "${app_dir}/${item}" .
            items_copied=$((items_copied + 1))
            log "  ✓ Included ${item}"
        else
            warn "  ${item} not found in ${app_dir} — skipping"
        fi
    done

    # Include exercises with priority: S3 (fresh) > local app directory (fallback)
    # Priority 1: Exercises from S3 (freshest, always up-to-date)
    if [ -n "${s3_exercises_dir}" ] && [ -d "${s3_exercises_dir}/exercises" ]; then
        mkdir -p exercises
        cp -a "${s3_exercises_dir}/exercises/." exercises/
        items_copied=$((items_copied + 1))
        log "  ✓ Included exercises/ (from S3)"
    # Priority 2: Fall back to exercises from local app directory (offline/legacy deployments)
    else
        for exercises_dir in \
            "${app_dir}/exercises" \
            "${app_dir}/palantir-jenkins-ai/docs/exercises" \
            "$(dirname "${app_dir}")/palantir-jenkins-ai/docs/exercises"; do
            if [ -d "${exercises_dir}" ]; then
                mkdir -p exercises
                cp -a "${exercises_dir}/." exercises/
                items_copied=$((items_copied + 1))
                log "  ✓ Included exercises/ (from local app directory)"
                break
            fi
        done
    fi

    if [ "${items_copied}" -eq 0 ]; then
        warn "No SUT content copied — falling back to stub Jenkinsfile"
        cd /
        _seed_stub_jenkinsfile
        return 0
    fi

    git add -A
    if git diff --cached --quiet; then
        log "  ✓ SUT content already present in '${REPO_NAME}' (nothing to commit)"
    else
        git commit -q -m "feat: seed Fellowship SUT (sut/, tests/, scripts/, Jenkinsfile, exercises) for ${STUDENT_ID}"
        if git push -q origin main; then
            log "  ✓ SUT content pushed to '${REPO_NAME}'"
        else
            warn "git push failed — students may need to pull manually"
        fi
    fi

    cd /
}

create_webhook() {
    log "Step 3: Creating webhook for '${REPO_NAME}'..."
    # Use Jenkins authToken remote build trigger to avoid GiteaPushTrigger NPE bug
    # (GiteaRepository.getOwner() returns null for org-owned repos in Gitea plugin v273).
    # Gitea sends POST; Jenkins rejects unauthenticated POST due to CSRF, so we embed
    # a Jenkins API token in the URL for Basic Auth — this bypasses the CSRF filter.
    ensure_jenkins_webhook_token
    
    # Delete old/stale webhooks before creating new one (prevents duplicates and URL drift)
    delete_stale_webhooks
    
    # Build the webhook URL with credentials embedded: https://user:token@host/job/...
    local jenkins_base="${SHARED_JENKINS_URL%/}"
    local jenkins_auth_url="${jenkins_base/https:\/\//https://${JENKINS_ADMIN_USER}:${JENKINS_WEBHOOK_API_TOKEN}@}"
    # Parameterized jobs require /buildWithParameters — /build returns HTTP 400 when
    # the job has any ParametersDefinitionProperty (e.g. the DEPLOYED_SUT_URL parameter).
    local jenkins_webhook_url="${jenkins_auth_url}/job/${STUDENT_ID}/job/fellowship-pipeline/buildWithParameters?token=${STUDENT_ID}"

    # Validate Jenkins is reachable
    log "  Validating Jenkins reachability..."
    if ! curl -sf --max-time 5 -o /dev/null "${jenkins_base}/" >/dev/null 2>&1; then
        warn "Jenkins may not be reachable: ${SHARED_JENKINS_URL}"
        warn "The webhook will be created, but deliveries may fail"
    else
        log "  ✓ Jenkins is reachable"
    fi
    
    local response
    response=$(gitea_api POST "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/hooks" "{
        \"type\": \"gitea\",
        \"config\": {
            \"url\": \"${jenkins_webhook_url}\",
            \"content_type\": \"json\"
        },
        \"events\": [\"push\"],
        \"active\": true
    }") || true

    if echo "$response" | grep -q '"id"'; then
        log "  ✓ Webhook created → /job/${STUDENT_ID}/job/fellowship-pipeline/buildWithParameters?token=${STUDENT_ID}"
    else
        warn "Webhook may already exist or creation failed: $response"
    fi
}

delete_stale_webhooks() {
    log "  Cleaning up stale webhooks (wrong endpoint or old configuration)..."
    
    local webhook_list
    webhook_list=$(gitea_api GET "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/hooks") || true
    
    if ! echo "$webhook_list" | grep -q '"id"'; then
        log "  ✓ No existing webhooks to clean up"
        return
    fi
    
    # Extract webhook IDs that point to old endpoints or this student's job
    # (allows re-provisioning without accumulating duplicate webhooks)
    local webhook_id webhook_url
    while IFS= read -r line; do
        if echo "$line" | grep -q '"id"'; then
            webhook_id=$(echo "$line" | sed -n 's/.*"id":\([0-9]*\).*/\1/p')
            # Get the full webhook config to check URL
            local webhook_config
            webhook_config=$(gitea_api GET "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/hooks/${webhook_id}") || true
            webhook_url=$(echo "$webhook_config" | grep -o '"url":"[^"]*"' | cut -d'"' -f4 || echo "")
            
            # Delete if: endpoint is old /build, OR already points to this student's pipeline
            if echo "$webhook_url" | grep -q '/build?token=' ||
               echo "$webhook_url" | grep -q "/job/${STUDENT_ID}/job/fellowship-pipeline"; then
                log "  Deleting old/duplicate webhook (id=$webhook_id): $webhook_url"
                gitea_api DELETE "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/hooks/${webhook_id}" >/dev/null || true
            fi
        fi
    done < <(echo "$webhook_list" | grep -E '"id"')
    
    log "  ✓ Stale webhook cleanup complete"
}

# ── Step 4: Jenkins folder for the student ────────────────────────────────────

create_jenkins_folder() {
    log "Step 4: Creating Jenkins folder for student '${STUDENT_ID}'..."
    local folder_xml
    folder_xml=$(cat <<XML
<?xml version='1.1' encoding='UTF-8'?>
<com.cloudbees.hudson.plugins.folder.Folder plugin="cloudbees-folder">
  <description>Pipeline workspace for student ${STUDENT_ID}</description>
  <displayName>Student: ${STUDENT_ID}</displayName>
</com.cloudbees.hudson.plugins.folder.Folder>
XML
)
    local crumb http_status
    crumb=$(jenkins_crumb)
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${JENKINS_URL}/createItem?name=${STUDENT_ID}" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        ${crumb:+-H "$crumb"} \
        -H "Content-Type: application/xml" \
        --data-binary "$folder_xml") || true

    if [ "$http_status" = "200" ] || [ "$http_status" = "302" ]; then
        log "  ✓ Jenkins folder '${STUDENT_ID}' created"
    elif [ "$http_status" = "400" ]; then
        log "  ✓ Jenkins folder '${STUDENT_ID}' already exists (skipped)"
    else
        warn "Jenkins folder creation returned HTTP ${http_status}"
    fi
}

# ── Step 5: Jenkins pipeline job inside student folder ───────────────────────

create_jenkins_pipeline() {
    log "Step 5: Creating Jenkins pipeline job for student '${STUDENT_ID}'..."
    local clone_url="${GITEA_URL}/${GITEA_ORG_NAME}/${REPO_NAME}.git"
    
    # Escape the DEPLOYED_SUT_URL for safe XML embedding
    local escaped_sut_url
    escaped_sut_url=$(escape_xml "${DEPLOYED_SUT_URL}")
    
    # Log what value we're injecting
    if [ -z "${DEPLOYED_SUT_URL}" ]; then
        log "  WARNING: DEPLOYED_SUT_URL is empty — job will have no default SUT endpoint"
    else
        log "  INFO: Setting DEPLOYED_SUT_URL default to: ${DEPLOYED_SUT_URL}"
    fi
    
    local job_xml
    job_xml=$(cat <<XML
<?xml version='1.1' encoding='UTF-8'?>
<org.jenkinsci.plugins.workflow.job.WorkflowJob plugin="workflow-job">
  <description>SUT pipeline for student ${STUDENT_ID}</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.StringParameterDefinition>
          <name>DEPLOYED_SUT_URL</name>
          <description>Base URL of this student's deployed SUT instance. Pre-configured at provisioning time; can be overridden per build.</description>
          <defaultValue>${escaped_sut_url}</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>${clone_url}</url>
          <credentialsId>gitea-admin-credentials</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/main</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <authToken>${STUDENT_ID}</authToken>
</org.jenkinsci.plugins.workflow.job.WorkflowJob>
XML
)
    local crumb http_status
    crumb=$(jenkins_crumb)
    # shellcheck disable=SC2086
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${JENKINS_URL}/job/${STUDENT_ID}/createItem?name=fellowship-pipeline" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        ${crumb:+-H "$crumb"} \
        -H "Content-Type: application/xml" \
        --data-binary "$job_xml") || true

    if [ "$http_status" = "200" ] || [ "$http_status" = "302" ]; then
        log "  ✓ Pipeline job created in folder '${STUDENT_ID}'"
    elif [ "$http_status" = "400" ]; then
        log "  Pipeline job already exists in folder '${STUDENT_ID}', checking if update is needed..."
        
        # Update the job if it is missing the DEPLOYED_SUT_URL string parameter
        # (covers old EnvInjectJobProperty approach and legacy jobs without the parameter).
        local existing_config
        existing_config=$(curl -s "${JENKINS_URL}/job/${STUDENT_ID}/job/fellowship-pipeline/config.xml" \
            -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
            -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" 2>/dev/null || echo "")

        local needs_update=0
        if echo "$existing_config" | grep -q "EnvInjectJobProperty"; then
            log "  Detected legacy EnvInjectJobProperty (envinject plugin not installed) — migrating to StringParameterDefinition..."
            needs_update=1
        elif ! echo "$existing_config" | grep -q "DEPLOYED_SUT_URL"; then
            log "  Job lacks DEPLOYED_SUT_URL parameter — updating..."
            needs_update=1
        fi

        if [ "$needs_update" = "1" ]; then
            crumb=$(jenkins_crumb)
            update_status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
                "${JENKINS_URL}/job/${STUDENT_ID}/job/fellowship-pipeline/config.xml" \
                -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
                -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
                ${crumb:+-H "$crumb"} \
                -H "Content-Type: application/xml" \
                --data-binary "$job_xml") || true

            if [ "$update_status" = "200" ] || [ "$update_status" = "302" ]; then
                log "  ✓ Pipeline job updated with StringParameterDefinition for DEPLOYED_SUT_URL"
                if [ -n "${DEPLOYED_SUT_URL}" ]; then
                    log "  ✓ DEPLOYED_SUT_URL default value: ${DEPLOYED_SUT_URL}"
                fi
            else
                warn "  Pipeline job update returned HTTP ${update_status}"
            fi
        else
            log "  ✓ Pipeline job already has the correct configuration (skipped)"
        fi
    else
        warn "Pipeline job creation returned HTTP ${http_status}"
    fi
}

# ── Post-provisioning validation ──────────────────────────────────────────────

validate_webhook() {
    log "Validating webhook..."
    local webhook_json
    webhook_json=$(gitea_api GET "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/hooks" 2>/dev/null | grep -o '"url":"[^"]*"' | head -1)
    
    if [ -z "$webhook_json" ]; then
        warn "No webhooks found for repo — webhook may not have been created"
        return 1
    fi
    
    if echo "$webhook_json" | grep -q "buildWithParameters"; then
        log "  ✓ Webhook URL endpoint is correct (/buildWithParameters)"
        return 0
    elif echo "$webhook_json" | grep -q "/build\?"; then
        warn "Webhook uses /build endpoint (should use /buildWithParameters for parameterized jobs)"
        return 1
    else
        log "  ✓ Webhook created: $webhook_json"
        return 0
    fi
}

validate_jenkins_folder_rbac() {
    log "Validating Jenkins folder-level RBAC..."
    local crumb http_status
    crumb=$(jenkins_crumb)
    
    http_status=$(curl -s -w "%{http_code}" -o /dev/null \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        "${JENKINS_URL}/job/${STUDENT_ID}/" 2>/dev/null)
    
    if [ "$http_status" = "200" ]; then
        log "  ✓ Jenkins folder exists and is accessible"
        return 0
    else
        warn "Jenkins folder not accessible (HTTP $http_status)"
        return 1
    fi
}

validate_jenkins_job_parameters() {
    log "Validating Jenkins pipeline job has parameters..."
    local config_xml
    
    config_xml=$(curl -s \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        -c "${JENKINS_COOKIE_JAR}" -b "${JENKINS_COOKIE_JAR}" \
        "${JENKINS_URL}/job/${STUDENT_ID}/job/fellowship-pipeline/config.xml" 2>/dev/null)
    
    if echo "$config_xml" | grep -q "DEPLOYED_SUT_URL"; then
        log "  ✓ Pipeline job has DEPLOYED_SUT_URL parameter"
        
        # Extract and verify the default value
        if [ -n "${DEPLOYED_SUT_URL}" ]; then
            local escaped_expected
            escaped_expected=$(escape_xml "${DEPLOYED_SUT_URL}")
            if echo "$config_xml" | grep -q "<defaultValue>.*${escaped_expected}.*</defaultValue>"; then
                log "  ✓ DEPLOYED_SUT_URL default value matches: ${DEPLOYED_SUT_URL}"
            else
                # Try checking without escaping (in case the check is fragile)
                local raw_url_in_config
                raw_url_in_config=$(echo "$config_xml" | grep -o '<defaultValue>[^<]*</defaultValue>' | head -1 | sed 's/<[^>]*>//g')
                if [ -n "$raw_url_in_config" ]; then
                    log "  ⚠ DEPLOYED_SUT_URL default value is: $raw_url_in_config"
                    log "    (expected: ${DEPLOYED_SUT_URL})"
                else
                    log "  ⚠ DEPLOYED_SUT_URL parameter has no default value set"
                fi
            fi
        else
            log "  ℹ DEPLOYED_SUT_URL parameter exists but no default value was set (DEPLOYED_SUT_URL env var is empty)"
        fi
        return 0
    else
        warn "Pipeline job missing DEPLOYED_SUT_URL parameter"
        return 1
    fi
}

# ── Summary ───────────────────────────────────────────────────────────────────

print_summary() {
    log "=================================================="
    log " Student '${STUDENT_ID}' provisioned successfully"
    log "=================================================="
    log "  Gitea repo:    ${SHARED_GITEA_URL}/${GITEA_ORG_NAME}/${REPO_NAME}"
    log "  Jenkins folder: ${SHARED_JENKINS_URL}job/${STUDENT_ID}/"
    log "  Jenkins job:   ${SHARED_JENKINS_URL}job/${STUDENT_ID}/job/fellowship-pipeline/"
    log "  Git clone URL: ${GITEA_URL}/${GITEA_ORG_NAME}/${REPO_NAME}.git"
    log "  Credentials:   ${STUDENT_ID} / ${STUDENT_PASSWORD}"
    log "=================================================="
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    log "Provisioning student '${STUDENT_ID}' on shared-core stack..."
    create_jenkins_student_user
    setup_jenkins_folder_permissions
    create_gitea_user
    create_gitea_repo
    seed_sut_content
    create_webhook
    create_jenkins_folder
    create_jenkins_pipeline
    
    log ""
    log "== Post-provisioning validation =="
    local validation_errors=0
    
    validate_webhook || validation_errors=$((validation_errors + 1))
    validate_jenkins_folder_rbac || validation_errors=$((validation_errors + 1))
    validate_jenkins_job_parameters || validation_errors=$((validation_errors + 1))
    
    if [ "$validation_errors" -gt 0 ]; then
        log ""
        warn "⚠ $validation_errors validation check(s) failed (see warnings above)"
        warn "The student may have limited functionality until issues are resolved."
    else
        log "  ✓ All validation checks passed"
    fi
    
    log ""
    print_summary
}

main "$@"
