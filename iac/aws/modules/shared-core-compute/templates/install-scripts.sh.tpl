#!/bin/bash
# Install shared-core provisioning scripts on instance startup.
# These scripts are called via SSM Run Command by the shared_core_provisioner Lambda.

mkdir -p /opt/scripts

cat > /opt/scripts/provision-student.sh << 'PROVISION_EOF'
${provision_script}
PROVISION_EOF

cat > /opt/scripts/deprovision-student.sh << 'DEPROVISION_EOF'
${deprovision_script}
DEPROVISION_EOF

chmod +x /opt/scripts/provision-student.sh /opt/scripts/deprovision-student.sh
