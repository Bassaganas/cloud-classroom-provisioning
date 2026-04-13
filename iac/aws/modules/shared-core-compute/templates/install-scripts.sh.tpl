#!/bin/bash
# Minimal bootstrap: create the scripts directory so the shared_core_provisioner
# Lambda can invoke scripts via SSM Run Command as soon as the instance registers.
# The actual script content is deployed by the deploy-shared-core workflow (git pull
# + SSH copy) to keep user data well under the 16 KB EC2 limit.
mkdir -p /opt/scripts

# Placeholder stubs — replaced by the deploy-shared-core workflow on first deploy.
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
