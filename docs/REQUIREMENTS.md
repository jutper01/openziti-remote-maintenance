# Technical Requirements & Design Document

## Project Overview
This document details the technical requirements, design decisions, and implementation approach for a zero-trust remote maintenance solution for OT environments using [OpenZiti](https://openziti.io).

## Goals
- Implement a working remote maintenance prototype using OpenZiti SDK and infrastructure
- Demonstrate identity-based, outbound-only connectivity for OT scenarios
- Provide multiple service types: command execution, file transfer, and port forwarding
- Deliver comprehensive benchmarking (latency, throughput, setup time) and security verification (port scanning, packet analysis)
- Create a clear demo with operator dashboard and performance metrics
- Keep hardware optional (IPC, SCALANCE, S7-1500 can be added later)

## Problem Statement
Industrial service engineers need secure remote access to OT devices (PLCs, HMIs, industrial PCs) for diagnostics, firmware updates, and configuration. Traditional approaches have significant drawbacks:

**Traditional VPN Approach:**
- Exposes entire network segments
- Requires firewall changes and port forwarding
- Broad network access even when only specific services are needed
- Complex certificate/credential management
- Attack surface: VPN endpoint becomes a target

**This Solution:**
- Service-level access (only specific functions exposed)
- No inbound connections or open ports on OT devices
- Identity-based authentication (no shared secrets)
- Zero-trust: verify identity for every connection
- Encrypted overlay network with built-in routing

## Use Case: Remote Maintenance Scenario

### Actors
- **Service Engineer (Operator)** - Maintenance personnel needing access
- **OT Device (Edge Agent)** - Industrial equipment requiring maintenance
- **OpenZiti Controller** - Manages identities, services, and policies

### Services Provided
1. **ops.exec** - Remote command execution
   - Allowlisted commands only (security constraint)
   - Execute diagnostics, restart services, check status
   - Example: `systemctl status plc-controller`, `df -h`, `uptime`

2. **ops.files** - Secure file transfer
   - Upload firmware updates, configuration files
   - Download logs, diagnostic reports
   - Integrity checks via checksums
   - Chunked transfer for large files

3. **ops.forward** - Port forwarding / tunneling
   - Access device's local web UI (e.g., HMI on localhost:8080)
   - Connect to internal services without exposing them externally
   - Example: Forward localhost:3000 → device's localhost:8080
   - Implementation notes (prototype): Implemented as a raw-TCP tunnel. The edge agent opens a local TCP connection to a configured default target (controlled via `OPS_FORWARD_DEFAULT_TARGET_HOST` and `OPS_FORWARD_DEFAULT_TARGET_PORT`) and relays bytes bidirectionally. The operator runs a local forward listener that accepts client connections and tunnels raw TCP into the `ops.forward` service.
   - Security controls: The agent enforces `OPS_FORWARD_ALLOWED_HOSTS` and `OPS_FORWARD_ALLOWED_PORTS` allowlists to limit accessible targets. The controller still governs which identities may dial or bind the forward service.

### Workflow
1. Operator authenticates with their OpenZiti identity
2. Operator dials a service (e.g., ops.exec)
3. Controller validates: Does this identity have permission to dial this service?
4. Controller connects Operator to Edge Agent via encrypted overlay
5. Edge Agent validates: Does this identity have permission to access my bound service?
6. Connection established - service executes (command runs, file transfers, port forwards)

## Architecture

### Conceptual Overview
```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Operator App   │◄───────►│  OpenZiti        │◄───────►│   Edge Agent    │
│ (Dashboard/CLI) │  Dials  │  Overlay Network │  Binds  │  (OT Device)    │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                    │
                            ┌───────┴────────┐
                            │   Controller   │
                            │   ZAC Console  │
                            └────────────────┘
```

**Key Concepts:**
- **Bind** - Edge Agent hosts/provides services
- **Dial** - Operator consumes/accesses services
- **Controller** - Manages identities, policies, routing
- **Overlay Network** - Encrypted tunnels, no direct IP connectivity

### Design Decisions

#### Why OpenZiti?
- **Open source** - No vendor lock-in, inspectable code
- **Zero-trust by default** - Identity verification on every connection
- **Service-oriented** - Granular access control per service
- **No infrastructure changes** - No firewall rules, no port forwarding
- **Outbound-only** - OT devices never accept incoming connections

#### Docker Lab vs Real Hardware
**Prototype Phase (Current):**
- Docker Compose for quick iteration
- Python 3.12 slim containers simulate OT devices
- All components on single host for development

**Production Deployment (Future):**
- OpenZiti controller remains centralized (cloud or on-premise)
- Edge Agent runs on industrial gateway or directly on capable PLCs
- Operator dashboard runs on engineer workstations

#### SDK Selection: Python
This prototype uses the Python SDK (`openziti`) for both the agent and the CLI.

## Security Considerations

### Identity & Authentication
- **Cryptographic identities** - X.509 certificates, no passwords
- **Enrollment process** - One-time JWT token → permanent identity certificate
- **Private keys** - Generated on device, never transmitted

### Authorization & Policies
- **Service Policies** - Define who can access what (bind/dial)
- **Edge Router Policy** - The setup script creates service-edge-router-policies so services can reach routers

### Operational Security
- **Command allowlisting** - ops.exec only runs pre-approved commands
- **Audit logging** - Agent emits structured JSON responses for operator actions

## Implementation Details

### Technology Stack
| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Controller | OpenZiti quickstart (Docker) | Official image, includes routing |
| Admin UI | ZAC (Ziti Admin Console) | Web-based management |
| Edge Agent | Python 3.12 slim | Lightweight, good SDK support |
| Operator CLI | Python 3.12 slim | Simple CLI used for testing/demos |
| Infrastructure | Docker Compose | Fast iteration, easy cleanup |

## Operational notes

- Reuse a single unpacked identity when creating multiple Ziti bindings in the same process. Re-initializing or reloading identities across bindings can trigger native SDK "invalid state" errors (observed as native error -22). Loading the identity once and reusing it for multiple bindings avoids this issue.
- When updating forwarding code or switching protocols (JSON-header framing vs raw-TCP), ensure both agent and operator are updated and restarted so they use the same protocol. Mismatched protocols will result in parsing errors or broken connections.
