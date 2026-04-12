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

# ── Step 2.5: Seed Jenkinsfile into student repo ─────────────────────────────

seed_jenkinsfile() {
    log "Step 2.5: Seeding Jenkinsfile into '${REPO_NAME}'..."

    # Base64-encode the Jenkinsfile content (Gitea contents API requires base64)
    local content
    content=$(printf '%s' "pipeline {
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
                        echo \"No package.json found, skipping npm build\"
                    fi
                '''
            }
        }
    }

    post {
        always {
            echo \"Pipeline complete for student ${STUDENT_ID}\"
        }
    }
}
" | base64 | tr -d '\n')

    local response
    response=$(gitea_api PUT "/repos/${GITEA_ORG_NAME}/${REPO_NAME}/contents/Jenkinsfile" "{
        \"message\": \"chore: seed Jenkinsfile for fellowship pipeline\",
        \"content\": \"${content}\"
    }") || true

    if echo "$response" | grep -q '"content"'; then
        log "  ✓ Jenkinsfile seeded into '${REPO_NAME}'"
    else
        warn "Jenkinsfile seed may have failed or already exists: $response"
    fi
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
    local clone_url="${GITEA_INTERNAL_URL}/${GITEA_ORG_NAME}/${REPO_NAME}.git"
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
    log "  Git clone URL: ${GITEA_INTERNAL_URL}/${GITEA_ORG_NAME}/${REPO_NAME}.git"
    log "  Credentials:   ${STUDENT_ID} / ${STUDENT_PASSWORD}"
    log "=================================================="
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    log "Provisioning student '${STUDENT_ID}' on shared-core stack..."
    create_gitea_user
    create_gitea_repo
    seed_jenkinsfile
    create_webhook
    create_jenkins_folder
    create_jenkins_pipeline
    print_summary
}

main "$@"
