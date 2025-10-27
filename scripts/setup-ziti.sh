#!/bin/bash
# Setup script for OpenZiti network configuration
# Run this INSIDE the controller container after: 
# docker exec -it openziti-ziti-controller-1 bash
# zitiLogin

set -euo pipefail

CONFIG_DIR="/ziti-config"

echo "=================================="
echo "OpenZiti Identity & Service Setup"
echo "=================================="
echo ""

# Clean up old enrollment files from previous runs
echo "🧹 Cleaning up old enrollment files..."
rm -f ${CONFIG_DIR}/edge-device.jwt ${CONFIG_DIR}/edge-device.json
rm -f ${CONFIG_DIR}/operator.jwt ${CONFIG_DIR}/operator.json
echo "✅ Cleanup complete"

echo ""
echo "📋 Step 1: Creating Identities"
echo "--------------------------------"

# Create edge-device identity
echo "Creating 'edge-device' identity"
ziti edge create identity "edge-device" -o ${CONFIG_DIR}/edge-device.jwt
echo "✅ edge-device identity created"

echo ""

# Create operator identity
echo "Creating 'operator' identity"
ziti edge create identity "operator" -o ${CONFIG_DIR}/operator.jwt
echo "✅ operator identity created"

echo ""
echo "📋 Step 2: Creating Services"
echo "--------------------------------"

echo "Creating service 'ops.exec' (remote command execution)..."
ziti edge create service "ops.exec"
echo "✅ ops.exec created"

echo ""
echo "Creating service 'ops.files' (file transfer)..."
ziti edge create service "ops.files"
echo "✅ ops.files created"

echo ""
echo "Creating service 'ops.forward' (port forwarding)..."
ziti edge create service "ops.forward"
echo "✅ ops.forward created"

echo ""
echo "📋 Step 3: Creating Service Policies"
echo "--------------------------------"

# Bind policy: edge-device can host (bind) all services
echo "Creating Bind policy 'edge-device-bind'..."
ziti edge create service-policy "edge-device-bind" Bind \
  --identity-roles '@edge-device' \
  --service-roles '#all'
echo "✅ edge-device-bind created"

echo ""

# Dial policy: operator can connect to (dial) all services
echo "Creating Dial policy 'operator-dial'..."
ziti edge create service-policy "operator-dial" Dial \
  --identity-roles '@operator' \
  --service-roles '#all'
echo "✅ operator-dial created"

echo ""
echo "📋 Step 4: Enrolling Identities"
echo "--------------------------------"

# Enroll edge-device identity
echo "Enrolling 'edge-device' identity..."
ziti edge enroll \
  --jwt ${CONFIG_DIR}/edge-device.jwt \
  --out ${CONFIG_DIR}/edge-device.json
echo "✅ edge-device enrolled -> ${CONFIG_DIR}/edge-device.json"

echo ""

# Enroll operator identity
echo "Enrolling 'operator' identity..."
ziti edge enroll \
  --jwt ${CONFIG_DIR}/operator.jwt \
  --out ${CONFIG_DIR}/operator.json
echo "✅ operator enrolled -> ${CONFIG_DIR}/operator.json"

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "📊 Summary:"
echo "  Identities created & enrolled:"
echo "    - edge-device (${CONFIG_DIR}/edge-device.json)"
echo "    - operator (${CONFIG_DIR}/operator.json)"
echo "  Services:"
echo "    - ops.exec"
echo "    - ops.files"
echo "    - ops.forward"
echo "  Policies:"
echo "    - edge-device-bind (Bind)"
echo "    - operator-dial (Dial)"
echo ""
echo "⚠️  SECURITY NOTE:"
echo "  The .json files contain private keys and should be protected."
echo "  They are stored in ${CONFIG_DIR} which is mounted in edge-device and operator containers."
echo ""
echo "🔍 Verify in ZAC: https://localhost:8443 or via CLI:"
echo "  ziti edge list identities"
echo "  ziti edge list services"
echo "  ziti edge list service-policies"
echo ""
