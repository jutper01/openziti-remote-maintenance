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
│  (Dashboard)    │  Dials  │  Overlay Network │  Binds  │  (OT Device)    │
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
- Alpine Linux containers simulate OT devices
- All components on single host for development

**Production Deployment (Future):**
- OpenZiti controller remains centralized (cloud or on-premise)
- Edge Agent runs on industrial gateway or directly on capable PLCs
- Operator dashboard runs on engineer workstations
- Optional: Deploy to real Siemens hardware (PLC + HMI via TIA Portal)

#### SDK Selection: Python vs Node.js
**Criteria:**
- OpenZiti SDK availability and maturity
- Ease of development for prototype
- Performance (latency, throughput)
- OT compatibility (can it run on industrial hardware?)

**Decision:** TBD - Will evaluate both:
- **Python** - `openziti-python` SDK, good for scripting, widely used in OT automation
- **Node.js** - `@openziti/ziti-sdk-nodejs`, async-first, good for dashboards

#### Simplified Architecture (No Separate Router)
- Controller includes built-in routing for prototype
- Simplifies deployment and reduces moving parts
- Sufficient for single-device proof of concept
- Production: Add dedicated edge routers for scale and redundancy

## Security Considerations

### Identity & Authentication
- **Cryptographic identities** - X.509 certificates, no passwords
- **Enrollment process** - One-time JWT token → permanent identity certificate
- **Private keys** - Generated on device, never transmitted
- **Mutual TLS** - Both client and server authenticate

### Authorization & Policies
- **Service Policies** - Define who can access what
  - Bind policies: Which identities can host services
  - Dial policies: Which identities can access services
- **Role-based selectors** - `@identity-name` or `#role-tag`
- **Least privilege** - Only grant necessary permissions

### Network Security
- **No open ports** - Edge devices make outbound connections only
- **Encrypted overlay** - All traffic encrypted end-to-end
- **No direct IP routing** - Controller mediates all connections
- **Attack surface** - Minimal: only outbound HTTPS to controller

### Operational Security
- **Command allowlisting** - ops.exec only runs pre-approved commands
- **File integrity** - Checksums verify uploads/downloads
- **Audit logging** - Track all service access attempts
- **Session management** - Time-limited connections, automatic cleanup

## Implementation Details

### Technology Stack
| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Controller | OpenZiti quickstart (Docker) | Official image, includes routing |
| Admin UI | ZAC (Ziti Admin Console) | Web-based management, built-in |
| Edge Agent | Python or Node.js + OpenZiti SDK | TBD based on SDK evaluation |
| Operator Dashboard | Python or Node.js + Web UI | TBD - CLI first, then web interface |
| Infrastructure | Docker Compose | Fast iteration, easy cleanup |

### Agent Implementation (Planned)
```python
# Pseudocode for edge agent
from openziti import zitiContext

# Load enrolled identity
context = zitiContext('/ziti-config/edge-device.json')

# Bind services
context.bind('ops.exec', handle_exec)
context.bind('ops.files', handle_files)
context.bind('ops.forward', handle_forward)

# Run event loop
context.run()
```

### Operator Dashboard (Planned)
- **Phase 1:** CLI tool for testing
  - `./operator.py exec "uptime"`
  - `./operator.py upload firmware.bin`
  - `./operator.py forward 3000:8080`
  
- **Phase 2:** Web UI for usability
  - React/Vue dashboard
  - Real-time command output
  - File upload/download progress
  - Connection status indicators

## Verification & Benchmarking

### Security Verification
1. **Port Scan (Nmap)**
   - Before: Scan edge device directly
   - After: Scan with OpenZiti (should show no open ports)
   - Expected: All services hidden behind overlay

2. **Traffic Analysis (Wireshark)**
   - Capture packets during service usage
   - Verify encryption (no plaintext commands/data)
   - Confirm only HTTPS to controller visible

3. **Attack Simulation**
   - Attempt unauthorized service access
   - Test identity theft scenarios
   - Verify policy enforcement

### Performance Benchmarking
1. **Latency**
   - Measure p50, p95, p99 for command execution
   - Compare: Direct SSH vs OpenZiti overlay
   - Target: < 100ms overhead for typical commands

2. **Throughput**
   - File transfer speed (MB/s)
   - Large file handling (100MB+)
   - Chunked transfer efficiency

3. **Connection Setup**
   - Time to establish overlay connection
   - Identity verification overhead
   - Service binding/dialing latency

4. **Resource Usage**
   - Agent CPU/memory footprint
   - Controller resource requirements
   - Scalability: 1 device vs 10 vs 100

### Operational Metrics
- Setup complexity (steps to deploy)
- Maintenance overhead
- Troubleshooting ease
- Compare to VPN-based approach

## Future Enhancements

### Additional Services
- **ops.telemetry** - Stream sensor data to cloud
- **ops.backup** - Automated configuration backups
- **ops.update** - Managed firmware deployment

### Monitoring & Observability  
- Grafana dashboards for overlay metrics
- Prometheus for controller health
- Distributed tracing for service calls

### Advanced Features
- Multi-device management (fleet operations)
- Role-based access control (engineer levels)
- Time-based access (temporary permissions)
- Approval workflows (two-person rule)

### Hardware Integration (Optional)
- Deploy to Siemens S7-1500 PLC
- Industrial gateway with OpenZiti agent
- TIA Portal integration for HMI
- S7 protocol communication
- Real OT network testing behind SCALANCE router