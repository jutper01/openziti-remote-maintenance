# Zero-Trust Remote Maintenance for OT Environments

A prototype demonstrating secure remote maintenance of industrial devices using [OpenZiti](https://openziti.io)'s zero-trust networking. This solution enables service engineers to securely access OT devices for diagnostics, firmware updates, and configuration—**without VPNs or exposed network ports**.

## 🎯 Key Features

- **Identity-Based Access** - No passwords, only cryptographic identities
- **Outbound-Only Connections** - Edge devices never accept incoming connections
- **Service-Level Security** - Granular control over who can access what
- **Zero Network Exposure** - No open ports, eliminates attack surface
- **End-to-End Encryption** - All traffic encrypted by default

## 🏗️ Architecture

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
- **Bind** - Edge device hosts services (ops.exec, ops.files, ops.forward)
- **Dial** - Operator connects to services through zero-trust overlay
- **No Open Ports** - All connections are outbound-only from edge device

## 🔧 Services Implemented

| Service | Purpose | Status |
|---------|---------|--------|
| `ops.exec` | Remote command execution with allowlist | 🚧 Planned |
| `ops.files` | Secure bidirectional file transfer | 🚧 Planned |
| `ops.forward` | Port forwarding to access local UIs | 🚧 Planned |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Get Started in 3 Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/jutper01/openziti-remote-maintenance.git
   cd openziti-remote-maintenance
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env if needed (defaults work for local testing)
   ```

3. **Start the environment**
   ```bash
   docker-compose up -d
   ```

4. **Access ZAC (Admin Console)**
   - Open: https://localhost:8443
   - Login: `admin` / `admin` (or your `.env` password)

📖 **For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md)**

## 📁 Project Structure

```
.
├── docker-compose.yaml     # Docker environment setup
├── .env.example           # Environment configuration template
├── QUICKSTART.md          # Detailed setup guide
├── edge-agent/            # Edge device agent (binds services)
├── operator-dashboard/    # Operator UI (dials services)
├── ziti-config/          # OpenZiti configuration & identities
├── scripts/              # Utility scripts
├── benchmarks/           # Performance test results
└── docs/                 # Additional documentation
    └── REQUIREMENTS.md   # Detailed project requirements
```

## ✅ Project Status

**Current Phase:** Docker Environment Setup ✅

- [x] Docker Compose environment with OpenZiti controller
- [x] ZAC (Admin Console) web interface
- [x] Edge device and operator dashboard containers
- [ ] OpenZiti identities and service definitions
- [ ] Edge agent implementation
- [ ] Operator dashboard implementation
- [ ] Hardware integration (Siemens PLC & HMI deployment)
- [ ] Security verification & benchmarking

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Step-by-step setup guide
- **[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)** - Detailed project requirements and design
- **[OpenZiti Documentation](https://openziti.io/)** - Official OpenZiti docs

## 🔒 Security Features

- **No Open Ports** - Edge devices maintain only outbound connections
- **Identity-Based** - Cryptographic identities, no shared secrets
- **End-to-End Encryption** - All traffic encrypted in transit
- **Service Segmentation** - Granular access control per service
- **Audit Logging** - Complete activity tracking

## 🧪 Verification & Testing (Planned)

- **Security:** Nmap port scans, Wireshark packet analysis
- **Performance:** Latency (p50/p95/p99), throughput, connection time
- **Operational:** Setup complexity vs traditional VPN

## 🤝 Contributing

This is a research/prototype project. Issues and suggestions are welcome!

## 🔗 References

- [OpenZiti GitHub](https://github.com/openziti/ziti)
- [OpenZiti Documentation](https://netfoundry.io/docs/openziti/learn/introduction/)
- [Zero Trust Architecture](https://www.nist.gov/publications/zero-trust-architecture)

## 💡 Future Enhancements

- Add ops.telemetry service for sensor data streaming
- Integrate Grafana/Prometheus monitoring
- Multi-device management dashboard
- Role-based access control
