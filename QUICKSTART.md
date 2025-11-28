# Getting Started with OpenZiti Environment

This guide walks you through setting up a minimal OpenZiti environment for the remote maintenance prototype.

## Prerequisites

- Docker and Docker Compose installed
- Ports 1280, 6262, 8443, and 3000 available on your host

## Step 1: Start the Environment

```bash
docker compose up -d
```

This will start:
- **ziti-controller** - OpenZiti controller
- **ziti-console** - ZAC web UI for administration
- **edge-device** - Simulated OT device container (placeholder for agent)
- **operator-dashboard** - Maintenance UI container (placeholder for dashboard)
- **ziti-router** - OpenZiti edge router (data-plane)

It will also create:
- `ziti-network` - Docker bridge network for container communication
- `ziti-fs` - Persistent volume for OpenZiti data and PKI certificates

## Step 2: Verify Services are Running

```bash
docker compose ps
```

You should see all services with "Up" status:
```
NAME                 STATUS
edge-device          Up
ziti-controller      Up (healthy)
operator-dashboard   Up
ziti-console         Up
ziti-router          Up
```

⏱️ **Wait 30-60 seconds** for the controller to fully initialize on first start.

## Step 3: Access ZAC (Admin Console)

Open your browser to: **https://localhost:8443**

**Login credentials:**
- Username: `admin`
- Password: `admin` (or whatever you set in `.env`)

⚠️ **Certificate Warning:** You'll see a security warning about a self-signed certificate. This is expected for local development. Click "Advanced" → "Proceed to localhost (unsafe)"

You should be greeted by the ZAC dashboard.

## Step 4: Test the Controller CLI

Verify you can interact with the controller using the CLI:

```bash
docker exec -it openziti-ziti-controller-1 bash
zitiLogin
```

You should see: `Token: <token-value>` and `Saving identity 'default' to...`

✅ **If ZAC is accessible and CLI commands work, your environment is ready for setup!**

## Step 5: Create Identities and Services

Now that the infrastructure is running, create the OpenZiti identities, services, and policies:

```bash
# If not already inside the controller container, run:
docker exec -it openziti-ziti-controller-1 bash

# Login to the controller
zitiLogin

# Run the setup script
/var/local/scripts/setup-ziti.sh
```

The script will:
1. **Clean up** - Remove any old configurations from previous runs
2. **Create identities** - `edge-device` (type: device) and `operator` (type: user)
3. **Create services** - `ops.exec`, `ops.files`, `ops.forward`
4. **Create policies** - Bind policy (edge-device can host services) and Dial policy (operator can access services)
5. **Create service edge router policy** - Assign all edge routers to all services
6. **Enroll identities** - Generate certificate-based identity files

### Verify in ZAC

After running the script, refresh ZAC (https://localhost:8443) and verify:

- **Identities** → Should show `edge-device` and `operator`
- **Services** → Should show `ops.exec`, `ops.files`, `ops.forward`
- **Service Policies** → Should show `edge-device-bind` and `operator-dial`

### Verify via CLI

Or verify from the command line:

```bash
# List identities (should show Default Admin, ziti-router (online), edge-device and operator)
ziti edge list identities

# List services (should show ops.exec, ops.files, ops.forward)
ziti edge list services

# List policies (should show edge-device-bind and operator-dial)
ziti edge list service-policies

# List service edge router policies (should show all edge routers assigned to all services)
ziti edge list service-edge-router-policies
```

✅ **Identity and service configuration complete!**

## Step 6: Start the Edge Agent and Operator CLI

With identities and services created, start the edge agent inside the `edge-device` container and the operator CLI inside the `operator-dashboard` container. Note: Run the following `docker compose` commands from the project root (where `docker-compose.yaml` is located).

1. Start the edge agent (runs in foreground; use `sh` in the container):

```bash
docker compose exec edge-device sh -lc '/var/local/scripts/start-edge-agent.sh'
```

The script creates a Python venv, installs dependencies, and binds the `ops.exec` service. It also ensures native OS libraries required by the OpenZiti Python SDK are present.

2. Start the operator CLI (interactive shell with venv activated):

```bash
docker compose exec -it operator-dashboard /var/local/scripts/start-operator-cli.sh
```

The operator startup script will prepare a venv, install `openziti`, and drop you into a shell where the venv is activated. From there you can run the CLI:

```bash
# examples
python /app/operator_cli.py uname -a
python /app/operator_cli.py ls -la /app
python /app/operator_cli.py echo "Hello from operator"
python /app/operator_cli.py cat /app/edge_agent.py
```

3. Notes:
- The edge agent enforces a command allowlist. Adjust with `OPS_EXEC_ALLOWLIST` environment variable when starting the agent (comma-separated list).
- The agent attempts to clean up its Ziti binding (terminator) on clean shutdown (SIGINT/SIGTERM). If you see orphaned terminators, stopping the agent with Ctrl+C should remove them.

## Useful Commands

### Container Management
```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f ziti-controller
docker compose logs -f ziti-console

# Stop everything
docker compose down

# Stop and remove volumes (complete reset - loses all data!)
docker compose down -v

# Restart a specific service
docker compose restart ziti-controller

# Execute commands in a container
docker compose exec edge-device sh
docker compose exec ziti-controller bash
```

### OpenZiti CLI Commands
```bash
# Login to controller (from host)
docker compose exec ziti-controller bash
zitiLogin

# List identities
ziti edge list identities

# List services
ziti edge list services

# List policies
ziti edge list service-policies

# List service edge router policies
ziti edge list service-edge-router-policies
```

### Controller exits with error after `docker compose down` (without `-v`)
The controller fails because it finds inconsistent data from a previous run. During development, always use the `-v` flag to clean up volumes:

```bash
# Correct way to restart during development
docker-compose down -v
docker-compose up -d

# Then re-run setup script
docker exec -it openziti-ziti-controller-1 bash
zitiLogin
/scripts/setup-ziti.sh
```

Alternatively, use `restart` instead of `down/up` to keep data:
```bash
docker-compose restart ziti-controller
```

## Environment Details

### Ports Exposed
- `1280` - Controller Edge Management API
- `6262` - Controller Control Plane
- `8443` - ZAC Web Interface
- `3000` - Operator Dashboard (placeholder)

### Volumes
- `ziti-fs` - Persistent storage for:
  - Controller database
  - PKI certificates
  - Configuration files
  
### Network
- `ziti-network` - Bridge network connecting all containers
