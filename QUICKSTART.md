# Getting Started with OpenZiti Environment

This guide walks you through setting up a minimal OpenZiti environment for the remote maintenance prototype.

## Prerequisites

- Docker and Docker Compose installed
- Ports 1280, 6262, 8443, and 3000 available on your host

## Step 1: Start the Environment

```bash
docker-compose up -d
```

This will start:
- **ziti-controller** - OpenZiti controller
- **ziti-console** - ZAC web UI for administration
- **edge-device** - Simulated OT device container (placeholder for agent)
- **operator-dashboard** - Maintenance UI container (placeholder for dashboard)

It will also create:
- `ziti-network` - Docker bridge network for container communication
- `ziti-fs` - Persistent volume for OpenZiti data and PKI certificates

## Step 2: Verify Services are Running

```bash
docker-compose ps
```

You should see all 4 services with "Up" status:
```
NAME                 STATUS
ziti-controller      Up (healthy)
ziti-console         Up
edge-device          Up
operator-dashboard   Up
```

⏱️ **Wait 30-60 seconds** for the controller to fully initialize on first start.

## Step 3: Access ZAC (Admin Console)

Open your browser to: **https://localhost:8443**

**Login credentials:**
- Username: `admin`
- Password: `admin` (or whatever you set in `.env`)

⚠️ **Certificate Warning:** You'll see a security warning about a self-signed certificate. This is expected for local development. Click "Advanced" → "Proceed to localhost (unsafe)"

### What You'll See in ZAC

- **Dashboard** - Overview (currently empty - no services yet)
- **Identities** - Only "Default Admin" exists currently
- **Services** - Empty (we'll create ops.exec, ops.files, ops.forward later)
- **Edge Routers** - Empty (controller has built-in routing for our simple setup)
- **Policies** - Default policies only

## Step 4: Test the Controller CLI

Verify you can interact with the controller using the CLI:

```bash
docker exec -it openziti-ziti-controller-1 bash
zitiLogin
```

You should see: `Token: <token-value>` and `Saving identity 'default' to...`

### List Identities

```bash
ziti edge list identities
```

You should see the "Default Admin" identity.

✅ **If ZAC is accessible and CLI commands work, your environment is ready!**

## Next Steps

Now that the environment is running, proceed to:
1. **Create Identities** - For edge-device and operator
2. **Define Services** - ops.exec, ops.files, ops.forward
3. **Configure Policies** - Bind and dial permissions
4. **Implement Agent** - Python/Node.js SDK on edge-device
5. **Build Dashboard** - Web UI for operators

## Useful Commands

### Container Management
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f ziti-controller
docker-compose logs -f ziti-console

# Stop everything
docker-compose down

# Stop and remove volumes (complete reset - loses all data!)
docker-compose down -v

# Restart a specific service
docker-compose restart ziti-controller

# Execute commands in a container
docker-compose exec edge-device sh
docker exec -it openziti-ziti-controller-1 bash
```

### OpenZiti CLI Commands
```bash
# Login to controller
docker exec -it openziti-ziti-controller-1 bash
zitiLogin"

# List identities
ziti edge list identities

# List services
ziti edge list services

# List policies
ziti edge list service-policies
```

## Troubleshooting

### Controller won't start
1. Check if ports are already in use:
   ```bash
   lsof -i :1280
   lsof -i :6262
   ```
2. Check logs for errors:
   ```bash
   docker-compose logs ziti-controller
   ```
3. Try a fresh start (⚠️ this deletes all data):
   ```bash
   docker-compose down -v && docker-compose up -d
   ```

### Can't access ZAC at https://localhost:8443
1. Verify controller is healthy:
   ```bash
   docker-compose ps
   ```
   Look for "Up (healthy)" status on ziti-controller

2. Check ZAC logs:
   ```bash
   docker-compose logs ziti-console
   ```

3. Test if port is accessible:
   ```bash
   curl -k https://localhost:8443
   ```

4. Wait longer - controller takes 30-60 seconds to fully initialize on first start

5. Verify ZAC has access to certificates:
   ```bash
   docker exec openziti-ziti-console-1 ls -la /persistent/pki/
   ```

### Login to ZAC fails
- Check your password in `.env` file
- Default is `admin` / `admin`
- If you changed `ZITI_PWD`, use that password

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
