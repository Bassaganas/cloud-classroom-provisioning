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

# ── Helpers ──────────────────────────────────────────────────────────────────

jenkins_crumb() {
    curl -sf -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        "${JENKINS_URL}/crumbIssuer/api/json" 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['crumbRequestField']}:{d['crumb']}\")" \
        2>/dev/null || echo ""
}

# ── Step 0: Delete Jenkins user and permissions ──────────────────────────────

delete_jenkins_student_user() {
    log "Step 0a: Deleting Jenkins user '${STUDENT_ID}'..."
    
    # Delete student user via Jenkins Script Console
    local groovy_script
    groovy_script=$(cat <<'GROOVY'
import jenkins.model.Jenkins
import hudson.security.HudsonPrivateSecurityRealm

def jenkins = Jenkins.getInstance()
def realm = jenkins.getSecurityRealm()

if (realm instanceof HudsonPrivateSecurityRealm) {
    try {
        realm.deleteUser(STUDENT_ID)
        println("User " + STUDENT_ID + " deleted successfully")
    } catch (Exception e) {
        println("User " + STUDENT_ID + " not found or deletion failed: " + e.getMessage())
    }
} else {
    println("WARNING: Jenkins security realm is not HudsonPrivateSecurityRealm")
}
GROOVY
    )
    
    # Substitute variables
    groovy_script="${groovy_script//STUDENT_ID/$STUDENT_ID}"
    
    local response crumb
    crumb=$(jenkins_crumb)
    response=$(curl -sf -X POST "${JENKINS_URL}/scriptText" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        ${crumb:+-H "$crumb"} \
        --data-urlencode "script=${groovy_script}" 2>/dev/null) || true

    if echo "$response" | grep -q "deleted successfully\|not found"; then
        log "  ✓ Jenkins user '${STUDENT_ID}' deletion completed"
    else
        warn "Jenkins user deletion: $response"
    fi
}

remove_jenkins_folder_permissions() {
    log "Step 0b: Removing Jenkins folder permissions for '${STUDENT_ID}'..."
    
    # Remove folder permissions via Jenkins Script Console
    local groovy_script
    groovy_script=$(cat <<'GROOVY'
import hudson.security.AuthorizationStrategy
import com.cloudbees.hudson.plugins.rolestrategy.RoleBasedAuthorizationStrategy
import jenkins.model.Jenkins

def jenkins = Jenkins.getInstance()
def rbac = jenkins.getAuthorizationStrategy()

if (rbac instanceof RoleBasedAuthorizationStrategy) {
    def folderRoles = rbac.getRoles(RoleBasedAuthorizationStrategy.FOLDER)
    def studentRoleName = "student-" + STUDENT_ID
    
    // Remove the folder role if it exists
    folderRoles.removeIf { it.name == studentRoleName }
    rbac.roles.put(RoleBasedAuthorizationStrategy.FOLDER, folderRoles)
    
    // Remove role mapping from folder
    def folderMapping = rbac.getRoleMap(RoleBasedAuthorizationStrategy.FOLDER)
    if (folderMapping != null) {
        folderMapping.remove(STUDENT_ID)
    }
    
    println("Folder permissions for " + STUDENT_ID + " removed")
    jenkins.save()
} else {
    println("WARNING: Jenkins does not have Role-Based Strategy plugin")
}
GROOVY
    )
    
    # Substitute variables
    groovy_script="${groovy_script//STUDENT_ID/$STUDENT_ID}"
    
    local response crumb
    crumb=$(jenkins_crumb)
    response=$(curl -sf -X POST "${JENKINS_URL}/scriptText" \
        -u "${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}" \
        ${crumb:+-H "$crumb"} \
        --data-urlencode "script=${groovy_script}" 2>/dev/null) || true

    if echo "$response" | grep -q "removed\|WARNING"; then
        log "  ✓ Folder permissions removed for '${STUDENT_ID}'"
    else
        warn "Folder permission removal: $response"
    fi
}

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
    delete_jenkins_student_user
    remove_jenkins_folder_permissions
    delete_jenkins_folder
    delete_gitea_repo
    delete_gitea_user
    log "✓ Student '${STUDENT_ID}' deprovisioned"
}

main "$@"
