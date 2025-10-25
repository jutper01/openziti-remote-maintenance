# Zero-Trust Remote Maintenance for OT Environments

A prototype demonstrating secure remote maintenance using OpenZiti's zero-trust networking. This solution enables service engineers to securely access industrial devices for diagnostics, firmware updates, and configuration without VPNs or exposed network ports.

## 🎯 Project Goals

- Implement identity-based, outbound-only connectivity for OT scenarios
- Demonstrate secure remote command execution, file transfer, and port forwarding
- Eliminate traditional VPN infrastructure and firewall modifications
- Provide comprehensive security verification and performance benchmarking

## 🏗️ Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Operator App   │◄───────►│  OpenZiti        │◄───────►│   Edge Agent    │
│  (Dashboard)    │  Dials  │  Overlay Network │  Binds  │  (OT Device)    │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                    │
                            ┌───────┴────────┐
                            │   Controller   │
                            │   Edge Router  │
                            │   ZAC Console  │
                            └────────────────┘
```

## 📁 Project Structure

```
.
├── edge-agent/              # Edge device agent (binds services)
│   ├── src/
│   ├── config/
│   └── Dockerfile
├── operator-dashboard/      # Operator application (dials services)
│   ├── src/
│   ├── public/
│   └── Dockerfile
├── ziti-config/            # OpenZiti configuration files
│   ├── identities/
│   └── policies/
├── scripts/                # Setup and utility scripts
├── benchmarks/             # Performance test results
├── docs/                   # Additional documentation
├── docker-compose.yaml     # Lab environment setup
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Git
- (Optional) Hardware: Siemens IPC, SCALANCE router

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/openziti-remote-maintenance.git
   cd openziti-remote-maintenance
   ```

2. **Start OpenZiti infrastructure**
   ```bash
   docker-compose up -d
   ```

3. **Initialize Ziti network**
   ```bash
   ./scripts/setup-ziti.sh
   ```

4. **Start the edge agent**
   ```bash
   cd edge-agent
   # Setup instructions TBD
   ```

5. **Start the operator dashboard**
   ```bash
   cd operator-dashboard
   # Setup instructions TBD
   ```

## 🔧 Services

### ops.exec - Remote Command Execution
Execute allowlisted commands on edge devices for diagnostics and troubleshooting.

### ops.files - Secure File Transfer
Transfer files bidirectionally with integrity verification and chunked streaming.

### ops.forward - Port Forwarding
Access local web UIs and services through the zero-trust overlay.

## 📊 Benchmarking

Performance metrics include:
- Connection setup time
- Command execution latency (p50/p95)
- File transfer throughput
- Port forwarding latency

Results and analysis available in `/benchmarks`

## 🔒 Security Verification

- **Port Scanning:** Nmap scans showing no exposed ports
- **Traffic Analysis:** Wireshark captures verifying encryption
- **Identity Verification:** OpenZiti's identity-based access control
- **Audit Logging:** Complete session and command logging

## 📖 Documentation

- [Setup Guide](docs/SETUP.md)
- [Architecture Details](docs/ARCHITECTURE.md)
- [Security Model](docs/SECURITY.md)
- [API Reference](docs/API.md)
- [Hardware Integration](docs/HARDWARE.md)

## 🎬 Demo

See [Demo Script](docs/DEMO.md) for a complete walkthrough.

Video demonstration: [Link TBD]

## 🛠️ Technology Stack

- **OpenZiti:** Zero-trust overlay network
- **Agent/Operator:** Python or Node.js (TBD)
- **Dashboard:** Web-based UI (framework TBD)
- **Containers:** Docker & Docker Compose

## 🚧 Project Status

**Current Phase:** Initial Setup

- [x] Project requirements defined
- [x] Project structure created
- [ ] Docker Compose environment
- [ ] Edge agent implementation
- [ ] Operator dashboard implementation
- [ ] Service policies configuration
- [ ] Benchmarking suite
- [ ] Security verification
- [ ] Documentation
- [ ] Demo video

## 🤝 Contributing

This is a prototype/research project. Contributions and suggestions are welcome!

## 📝 License

[License TBD]

## 🔗 References

- [OpenZiti](https://github.com/openziti/ziti)
- [OpenZiti Documentation](https://openziti.io/)
- [Project Requirements](project-requirements.md)

## 💡 Future Enhancements

- Add ops.telemetry service for sensor data streaming
- Integrate Grafana/Prometheus monitoring
- Multi-device management dashboard
- Role-based access control
- Hardware integration guide
