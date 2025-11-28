#!/usr/bin/env bash
# Setup a Python venv, install deps, and start the operator CLI
# Intended to be run INSIDE the operator-dashboard container.
# In this project, this script is mounted at /var/local/scripts/start-operator-cli.sh

set -euo pipefail

VENV_DIR="${VENV_DIR:-/opt/venv}"
PY_BIN="${PYTHON_BIN:-python3}"
REQ_FILE="${REQ_FILE:-/app/requirements.txt}"
CLI_FILE="${CLI_FILE:-/app/operator_cli.py}"
IDENTITY_FILE="${ZITI_OPERATOR_IDENTITY:-/ziti-config/operator.json}"

echo "[operator-cli] ▶ Starting setup"

if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  echo "[operator-cli] ⚠️  $PY_BIN not found, trying 'python'"
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
      echo "[operator-cli] 📦 installing OS deps: $MISSING_PKGS"
      apt-get update -y
      # --no-install-recommends keeps the image lean
      apt-get install -y --no-install-recommends $MISSING_PKGS ca-certificates
      rm -rf /var/lib/apt/lists/*
      echo "[operator-cli] ✅ OS deps installed"
    else
      echo "[operator-cli] ✅ OS deps already present"
    fi
  else
    echo "[operator-cli] ℹ️  apt-get not available; assuming OS deps present"
  fi
}

ensure_os_deps

# Sanity checks
if [ ! -f "$REQ_FILE" ]; then
  echo "[operator-cli] ❌ requirements file not found: $REQ_FILE" >&2
  exit 1
fi
if [ ! -f "$CLI_FILE" ]; then
  echo "[operator-cli] ❌ CLI file not found: $CLI_FILE" >&2
  exit 1
fi
if [ ! -f "$IDENTITY_FILE" ]; then
  echo "[operator-cli] ⚠️  identity file not found yet: $IDENTITY_FILE"
  echo "[operator-cli]     Ensure you've run the Ziti setup and enrolled 'operator' before using the CLI."
fi

# 1) Create & activate venv
if [ ! -d "$VENV_DIR" ]; then
  echo "[operator-cli] 🧪 creating venv at $VENV_DIR"
  "$PY_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
echo "[operator-cli] ✅ venv activated: $VENV_DIR"

# 2) Install deps
python -m pip install --upgrade pip > /dev/null
pip install -q -r "$REQ_FILE"

echo "[operator-cli] ✅ dependencies installed"
echo "[operator-cli] ✅ Ready to execute commands"
echo ""
echo "Usage: python $CLI_FILE <command> [args...]"
echo ""
echo "Valid Examples:"
echo "  python $CLI_FILE uname -a"
echo "  python $CLI_FILE ls -la /app"
echo "  python $CLI_FILE echo 'Hello from operator'"
echo "Non-valid Examples:"
echo "  python $CLI_FILE cat /app/edge_agent.py"
echo ""

# Auto-activate venv in future bash sessions
if [ ! -f ~/.bashrc ] || ! grep -q "/opt/venv/bin/activate" ~/.bashrc 2>/dev/null; then
  echo "[ -f /opt/venv/bin/activate ] && . /opt/venv/bin/activate" >> ~/.bashrc
fi

# Drop into an interactive shell for manual CLI usage (venv already active)
exec bash -l
