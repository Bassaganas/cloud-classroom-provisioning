#!/bin/bash
# Bootstrap shared-core EC2 instance:
#   1. Install Docker + Docker Compose so services can start.
#   2. Create the /opt/scripts directory with placeholder stubs.
#
# The actual application deployment (Jenkins, Gitea, certs, .env) is performed
# by the deploy-shared-core workflow (SSH + git clone) after Terraform finishes.
# This script ensures Docker is ready BEFORE that workflow runs.
set -euo pipefail

exec > >(tee /var/log/user-data.log) 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting shared-core bootstrap..."

# ── Install Docker ────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Installing Docker..."
  amazon-linux-extras enable docker
  yum install -y docker
  systemctl enable --now docker
  usermod -aG docker ec2-user
fi

# ── Install Docker Compose v2 plugin ─────────────────────────────────────────
if ! docker compose version >/dev/null 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Installing Docker Compose plugin..."
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# ── Install git (needed by deploy-shared-core to clone the repo) ──────────────
if ! command -v git >/dev/null 2>&1; then
  yum install -y git
fi

# ── Placeholder provisioning scripts ─────────────────────────────────────────
mkdir -p /opt/scripts

cat > /opt/scripts/provision-student.sh << 'EOF'
#!/bin/bash
echo "[provision] Script not yet deployed. Run the deploy-shared-core workflow to install scripts." >&2
exit 1
EOF

cat > /opt/scripts/deprovision-student.sh << 'EOF'
#!/bin/bash
echo "[deprovision] Script not yet deployed. Run the deploy-shared-core workflow to install scripts." >&2
exit 1
EOF

chmod +x /opt/scripts/provision-student.sh /opt/scripts/deprovision-student.sh

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Shared-core bootstrap complete. Docker $(docker --version), Compose $(docker compose version)."
