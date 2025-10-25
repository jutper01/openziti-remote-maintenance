# Project Requirements: Zero-Trust Remote Maintenance for OT Environments
## Overview
This project demonstrates zero-trust networking for OT environments using https://github.com/openziti/ziti. It builds a prototype solution for secure remote maintenance that enables service-level access without exposing network ports or requiring VPN infrastructure.

## Goals
- Implement a working remote maintenance prototype using OpenZiti SDK and infrastructure
- Demonstrate identity-based, outbound-only connectivity for OT scenarios
- Provide multiple service types: command execution, file transfer, and port forwarding
- Deliver comprehensive benchmarking (latency, throughput, setup time) and security verification (port scanning, packet analysis)
- Create a clear demo with operator dashboard and performance metrics
- Keep hardware optional (IPC, SCALANCE, S7-1500 can be added later)

## Prototype: Remote Maintenance Solution
### Scenario
Service engineers need secure remote access to industrial devices for:
- Diagnostics
- Firmware updates
- Accessing local web UIs

Traditional VPN solutions expose networks and require firewall changes. This prototype uses OpenZiti to provide service-level access without open ports.

### Features
- **Agent (SDK TBD):**
    - Binds services: ops.exec, ops.files, ops.forward
    - Remote command execution (allowlist)
    - Secure file transfer (chunked, integrity check)
    - Optional port forwarding

- **Operator App (Python or Node):**

    - CLI + dashboard for actions
    - Metrics: connect time, latency, throughput

- **Overlay:**
    - Identity-based, outbound-only connections
    - Micro-segmentation via service policies

### Demo Flow
1. Access localhost UI through zero-trust overlay (no VPN, no open ports)
2. Change settings or behaviour & show results
3. Execute remote commands via operator dashboard
4. Transfer files securely between operator and edge device
5. Show Nmap scan (no open ports) and Wireshark capture (encrypted traffic)

## Architecture
- **Docker Compose Lab:**
    - OpenZiti controller, edge router, ZAC (admin console)
    - Simulated edge device container

- **Identities & Services:**
    - Edge device identity (binds services)
    - Operator identity (dials services)
    - Service definitions: ops.exec, ops.files, ops.forward
    - Service policies for micro-segmentation

- **Optional Hardware:**
    - IPC behind SCALANCE router for real-world OT scenario

## Implementation Details
### Technology Stack (TBD)
- **Agent:** Python or Node.js with OpenZiti SDK
- **Operator App:** Python or Node.js with CLI + web dashboard
- **Dashboard Framework:** Consider React, Vue, or terminal-based (e.g., blessed, ink)

### Security Considerations
- Command allowlisting with predefined safe commands
- File transfer with integrity checks (checksums)
- Session management and audit logging
- Identity verification and service authorization

## Verification & Benchmarking
- **Performance:**
    - Latency (p50/p95), throughput, connection setup time
- **Security:**
    - Nmap port scan (before/after Ziti)
    - Wireshark packet analysis (encrypted payload)
- **Operational Complexity:**
    - Steps required vs VPN-based solutions

## Deliverables
- Source code for edge agent and operator dashboard
- Docker Compose setup for complete OpenZiti lab environment
- Comprehensive benchmark report with graphs and analysis
- Demo script and recorded video walkthrough
- Documentation for setup and usage
- Optional: Hardware integration guide for IPC/SCALANCE devices

## Future Enhancements (Post-MVP)
- Add ops.telemetry service for streaming sensor data
- Integrate Grafana/Prometheus for monitoring
- Multi-device management in operator dashboard
- Role-based access control for different operator levels