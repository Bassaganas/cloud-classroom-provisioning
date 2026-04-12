#!/bin/bash
# deprovision-student.sh — Remove a student from the shared-core stack
#
# Removes:
#   1. Jenkins folder (and all jobs within it)
#   2. Gitea repo for the student
#   3. Gitea user account
#
# DESTRUCTIVE. Requires explicit --confirm flag.
#
# Usage:
#   bash deprovision-student.sh <student_id> --confirm
#
# Environment variables: same as provision-student.sh

set -euo pipefail

STUDENT_ID="${1:?Usage: deprovision-student.sh <student_id> --confirm}"
CONFIRM="${2:-}"

[ "${CONFIRM}" = "--confirm" ] || {
    echo "ERROR: Pass --confirm to acknowledge this is destructive" >&2
    exit 1
}

GITEA_URL="${GITEA_URL:-http://localhost:3030}"
GITEA_ADMIN_USER="${GITEA_ADMIN_USER:-fellowship}"
GITEA_ADMIN_PASSWORD="${GITEA_ADMIN_PASSWORD:-fellowship123}"
GITEA_ORG_NAME="${GITEA_ORG_NAME:-fellowship-org}"

JENKINS_URL="${JENKINS_URL:-http://localhost:8080}"
JENKINS_ADMIN_USER="${JENKINS_ADMIN_USER:-fellowship}"
JENKINS_ADMIN_PASSWORD="${JENKINS_ADMIN_PASSWORD:-fellowship123}"

REPO_NAME="fellowship-sut-${STUDENT_ID}"

log()  { echo "[deprovision] $*"; }
warn() { echo "[deprovision] WARNING: $*" >&2; }

# ── Step 1: Delete Jenkins folder ─────────────────────────────────────────────

delete_jenkins_folder() {
    log "Step 1: Deleting Jenkins folder '${STUDENT_ID}'..."
    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "${JENKINS_URL}/job/${STUDENT_ID}/doDelete" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}") || true

    if [ "$http_status" = "302" ] || [ "$http_status" = "200" ]; then
        log "  ✓ Jenkins folder '${STUDENT_ID}' deleted"
    elif [ "$http_status" = "404" ]; then
        log "  ✓ Jenkins folder '${STUDENT_ID}' not found (already removed)"
    else
        warn "Jenkins folder deletion returned HTTP ${http_status}"
    fi
}

# ── Step 2: Delete Gitea repo ─────────────────────────────────────────────────

delete_gitea_repo() {
    log "Step 2: Deleting Gitea repo '${GITEA_ORG_NAME}/${REPO_NAME}'..."
    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X DELETE "${GITEA_URL}/api/v1/repos/${GITEA_ORG_NAME}/${REPO_NAME}" \
        -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}") || true

    if [ "$http_status" = "204" ]; then
        log "  ✓ Gitea repo '${REPO_NAME}' deleted"
    elif [ "$http_status" = "404" ]; then
        log "  ✓ Gitea repo '${REPO_NAME}' not found (already removed)"
    else
        warn "Gitea repo deletion returned HTTP ${http_status}"
    fi
}

# ── Step 3: Delete Gitea user ─────────────────────────────────────────────────

delete_gitea_user() {
    log "Step 3: Deleting Gitea user '${STUDENT_ID}'..."
    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
        -X DELETE "${GITEA_URL}/api/v1/admin/users/${STUDENT_ID}" \
        -u "${GITEA_ADMIN_USER}:${GITEA_ADMIN_PASSWORD}") || true

    if [ "$http_status" = "204" ]; then
        log "  ✓ Gitea user '${STUDENT_ID}' deleted"
    elif [ "$http_status" = "404" ]; then
        log "  ✓ Gitea user '${STUDENT_ID}' not found (already removed)"
    else
        warn "Gitea user deletion returned HTTP ${http_status}"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    log "Deprovisioning student '${STUDENT_ID}' from shared-core stack..."
    delete_jenkins_folder
    delete_gitea_repo
    delete_gitea_user
    log "✓ Student '${STUDENT_ID}' deprovisioned"
}

main "$@"
