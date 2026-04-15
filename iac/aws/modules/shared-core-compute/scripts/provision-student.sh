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
STUDENT_PASSWORD="${2:-fellowship123}"

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

# Jenkins CSRF: session cookie jar shared across all Jenkins API calls
JENKINS_COOKIE_JAR="/tmp/jenkins-cookies-$$.txt"

REPO_NAME="fellowship-sut-${STUDENT_ID}"

log()  { echo "[provision] $*"; }
warn() { echo "[provision] WARNING: $*" >&2; }
die()  { echo "[provision] ERROR: $*" >&2; exit 1; }

# ── Helpers ───────────────────────────────────────────────────────────────────

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

# ── Step 1: Gitea student user ────────────────────────────────────────────────

create_gitea_user() {
    log "Step 1: Creating Gitea user '${STUDENT_ID}'..."
    local response
    response=$(gitea_api POST "/admin/users" "{
        \"login_name\": \"${STUDENT_ID}\",
        \"username\": \"${STUDENT_ID}\",
        \"password\": \"${STUDENT_PASSWORD}\",
        \"email\": \"${STUDENT_ID}@fellowship.local\",
        \"send_notify\": false,
        \"must_change_password\": false,
        \"source_id\": 0
    }") || true

    if echo "$response" | grep -q '"id"'; then
        log "  ✓ Gitea user '${STUDENT_ID}' created"
    else
        log "  ✓ Gitea user '${STUDENT_ID}' already exists (skipped)"
    fi
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
    trap "rm -rf '${tmp_dir}'" RETURN

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
    for item in sut tests Jenkinsfile pytest.ini; do
        if [ -e "${app_dir}/${item}" ]; then
            cp -a "${app_dir}/${item}" .
            items_copied=$((items_copied + 1))
            log "  ✓ Included ${item}"
        else
            warn "  ${item} not found in ${app_dir} — skipping"
        fi
    done

    # Include any exercises docs if present.
    # First check exercises/ directly in the app dir (preferred — committed to repo),
    # then fall back to palantir-jenkins-ai/docs/exercises for legacy layouts.
    for exercises_dir in \
        "${app_dir}/exercises" \
        "${app_dir}/palantir-jenkins-ai/docs/exercises" \
        "$(dirname "${app_dir}")/palantir-jenkins-ai/docs/exercises"; do
        if [ -d "${exercises_dir}" ]; then
            mkdir -p exercises
            cp -a "${exercises_dir}/." exercises/
            log "  ✓ Included exercises"
            break
        fi
    done

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
        git commit -q -m "feat: seed Fellowship SUT (sut/, tests/, Jenkinsfile) for ${STUDENT_ID}"
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
    local jenkins_webhook_url="${JENKINS_URL}/gitea-webhook/post"
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
        log "  ✓ Webhook created → ${jenkins_webhook_url}"
    else
        warn "Webhook may already exist or creation failed: $response"
    fi
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
    local job_xml
    job_xml=$(cat <<XML
<?xml version='1.1' encoding='UTF-8'?>
<org.jenkinsci.plugins.workflow.job.WorkflowJob plugin="workflow-job">
  <description>SUT pipeline for student ${STUDENT_ID}</description>
  <keepDependencies>false</keepDependencies>
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
  <triggers>
    <com.cloudbees.jenkins.plugins.gitea.GiteaPushTrigger plugin="gitea"/>
  </triggers>
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
        log "  ✓ Pipeline job already exists in folder '${STUDENT_ID}' (skipped)"
    else
        warn "Pipeline job creation returned HTTP ${http_status}"
    fi
}

# ── Summary ───────────────────────────────────────────────────────────────────

print_summary() {
    log "=================================================="
    log " Student '${STUDENT_ID}' provisioned successfully"
    log "=================================================="
    log "  Gitea repo:    ${SHARED_GITEA_URL}/${GITEA_ORG_NAME}/${REPO_NAME}"
    log "  Jenkins job:   ${SHARED_JENKINS_URL}job/${STUDENT_ID}/job/fellowship-pipeline/"
    log "  Git clone URL: ${GITEA_URL}/${GITEA_ORG_NAME}/${REPO_NAME}.git"
    log "  Credentials:   ${STUDENT_ID} / ${STUDENT_PASSWORD}"
    log "=================================================="
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    log "Provisioning student '${STUDENT_ID}' on shared-core stack..."
    create_gitea_user
    create_gitea_repo
    seed_sut_content
    create_webhook
    create_jenkins_folder
    create_jenkins_pipeline
    print_summary
}

main "$@"
