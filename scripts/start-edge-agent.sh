#!/usr/bin/env bash
# Setup a Python venv, install deps, and start the edge agent
# Intended to be run INSIDE the edge-device container.
# In this project, this script is mounted at /var/local/scripts/start-edge-agent.sh

set -euo pipefail

VENV_DIR="${VENV_DIR:-/opt/venv}"
PY_BIN="${PYTHON_BIN:-python3}"
REQ_FILE="${REQ_FILE:-/app/requirements.txt}"
AGENT_FILE="${AGENT_FILE:-/app/edge_agent.py}"
IDENTITY_FILE="${ZITI_EDGE_IDENTITY:-/ziti-config/edge-device.json}"

echo "[edge-agent] ▶ Starting setup"

if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  echo "[edge-agent] ⚠️  $PY_BIN not found, trying 'python'"
  PY_BIN=python
fi

# Ensure native OS dependencies for the OpenZiti SDK are present (Debian/Ubuntu)
ensure_os_deps() {
  # Only attempt if apt-get exists
  if command -v apt-get >/dev/null 2>&1; then
    MISSING_PKGS=""
    for pkg in libprotobuf-c1 libc-ares2 libuv1; do
      if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PKGS+="$pkg "
      fi
    done
    if [ -n "$MISSING_PKGS" ]; then
      echo "[edge-agent] 📦 installing OS deps: $MISSING_PKGS"
      apt-get update -y
      # --no-install-recommends keeps the image lean
      apt-get install -y --no-install-recommends $MISSING_PKGS ca-certificates
      rm -rf /var/lib/apt/lists/*
      echo "[edge-agent] ✅ OS deps installed"
    else
      echo "[edge-agent] ✅ OS deps already present"
    fi
  else
    echo "[edge-agent] ℹ️  apt-get not available; assuming OS deps present"
  fi
}

ensure_os_deps

# Sanity checks
if [ ! -f "$REQ_FILE" ]; then
  echo "[edge-agent] ❌ requirements file not found: $REQ_FILE" >&2
  exit 1
fi
if [ ! -f "$AGENT_FILE" ]; then
  echo "[edge-agent] ❌ agent file not found: $AGENT_FILE" >&2
  exit 1
fi
if [ ! -f "$IDENTITY_FILE" ]; then
  echo "[edge-agent] ⚠️  identity file not found yet: $IDENTITY_FILE"
  echo "[edge-agent]     Ensure you've run the Ziti setup and enrolled 'edge-device' before starting."
fi

# 1) Create & activate venv
if [ ! -d "$VENV_DIR" ]; then
  echo "[edge-agent] 🧪 creating venv at $VENV_DIR"
  "$PY_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
echo "[edge-agent] ✅ venv activated: $VENV_DIR"

# 2) Install deps
python -m pip install --upgrade pip
pip install -r "$REQ_FILE"

echo "[edge-agent] ✅ dependencies installed"

# Create a simple webroot and start a background HTTP server for demos
# This provides the edge-local hidden HTTP service at 127.0.0.1:8080
WEBROOT="/var/local/www"
LOGDIR="/var/local/logs"
mkdir -p "$WEBROOT" "$LOGDIR"
if [ ! -f "$WEBROOT/index.html" ]; then
  cat > "$WEBROOT/index.html" <<'HTML'
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Hidden HMI</title>
  </head>
  <body>
    <h1>Hidden HMI: Access Granted!</h1>
    <p>This page is served by the demo HTTP server started by <code>start-edge-agent.sh</code>.</p>
  </body>
</html>
HTML
  echo "[edge-agent] ✅ created $WEBROOT/index.html"
else
  echo "[edge-agent] ℹ️  $WEBROOT/index.html already exists; leaving intact"
fi

# Start a background HTTP server on 127.0.0.1:8080 serving $WEBROOT
# Use the active Python binary so the venv Python is used if available.
(
  cd "$WEBROOT" && "$PY_BIN" -m http.server 8080 > "$LOGDIR/http-server.log" 2>&1 &
)
echo "[edge-agent] ▶ started demo HTTP server at 127.0.0.1:8080 (logs: $LOGDIR/http-server.log)"

# 3) Start the agent
export PYTHONUNBUFFERED=1
echo "[edge-agent] ▶ launching agent: $AGENT_FILE"
exec python "$AGENT_FILE"
