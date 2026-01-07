# Docker Multi-Architecture Deployment Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Your NAS Device                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │            Docker Engine (linux/arm64 or amd64)            │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │      Crypto Transaction Tracker Container           │  │ │
│  │  │  ┌────────────────────────────────────────────────┐  │  │ │
│  │  │  │  Application (Python 3.11)                     │  │  │ │
│  │  │  │  • Flask Web Server (HTTPS)                    │  │  │ │
│  │  │  │  • CLI Interface                               │  │  │ │
│  │  │  │  • ML/AI Features (optional)                   │  │  │ │
│  │  │  │  • Health Check Endpoint                       │  │  │ │
│  │  │  └────────────────────────────────────────────────┘  │  │ │
│  │  │                                                       │  │ │
│  │  │  ┌────────────────────────────────────────────────┐  │  │ │
│  │  │  │  Volumes (Persistent Storage)                 │  │  │ │
│  │  │  │  • /app/configs/ → configs/                   │  │  │ │
│  │  │  │  • /app/inputs/ → inputs/                     │  │  │ │
│  │  │  │  • /app/outputs/ → outputs/                   │  │  │ │
│  │  │  │  • /app/processed_archive/                    │  │  │ │
│  │  │  │  • /app/certs/ (SSL certificates)             │  │  │ │
│  │  │  └────────────────────────────────────────────────┘  │  │ │
│  │  │                                                       │  │ │
│  │  │  Resource Limits:                                    │  │ │
│  │  │  • CPU: 2.0 (configurable)                          │  │ │
│  │  │  • RAM: 2GB (configurable)                          │  │ │
│  │  │  • Auto-restart on failure                          │  │ │
│  │  │  • Health check every 30s                           │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          ▲                                       │
│                          │                                       │
│         ┌────────────────┼────────────────┐                     │
│         │                │                │                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Port      │  │  Security   │  │ Networking  │             │
│  │             │  │             │  │             │             │
│  │ 5000:5000   │  │ • HTTPS SSL │  │ Bridge Mode │             │
│  │   (HTTPS)   │  │ • Non-root  │  │ • Firewall  │             │
│  │             │  │ • No priv   │  │ • Isolated  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                           ▲
                           │
            ┌──────────────┴──────────────┐
            │                             │
      ┌─────────────┐             ┌─────────────┐
      │   Browser   │             │   CLI       │
      │             │             │             │
      │ Web UI @    │             │ docker exec │
      │ :5000       │             │ commands    │
      │ HTTPS       │             │             │
      └─────────────┘             └─────────────┘
```

## Multi-Architecture Build Pipeline

```
┌────────────────────────────────────────────────┐
│          Build Multi-Arch Image                │
│  ./build-multiarch.sh or .\build-multiarch.ps1 │
└────────────────────┬─────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
    ┌─────────────┐         ┌─────────────┐
    │  linux/amd64 │        │ linux/arm64 │
    │  (x86_64)    │        │ (aarch64)   │
    │              │        │             │
    │ • Synology   │        │ • Synology  │
    │ • QNAP       │        │ • QNAP      │
    │ • Asustor    │        │ • Rasp Pi   │
    │ • UGREEN     │        │ • Apple M1  │
    │ • Linux      │        │ • Other ARM │
    │ • Docker DT  │        │             │
    └─────┬───────┘        └─────┬───────┘
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
        ┌──────────────────────────┐
        │   Single Multi-Arch      │
        │   Docker Image           │
        │   crypto-tracker:latest  │
        └──────────────┬───────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
   ┌─────────────┐            ┌─────────────┐
   │   Deploy    │            │   Push to   │
   │   Locally   │            │   Registry  │
   │             │            │  (Optional) │
   │ docker-     │            │             │
   │ compose up  │            │ ghcr.io or  │
   │             │            │ Docker Hub  │
   └─────────────┘            └─────────────┘
```

## Deployment Flow by NAS Type

### UGREEN NAS (SSH-Based) ⭐

```
┌─────────────────────────────────────────┐
│   Your Computer                         │
└─────────────────────────────────────────┘
              │
              │ SSH Terminal
              ▼
┌─────────────────────────────────────────┐
│   UGREEN NAS Web Interface              │
│   • Enable SSH                          │
│   • Check port (usually 22 or 2222)     │
└─────────────────────────────────────────┘
              │
              │ SSH Connection
              ▼
┌─────────────────────────────────────────┐
│   UGREEN NAS CLI                        │
│   $ mkdir /mnt/docker/crypto-tracker    │
│   $ cd /mnt/docker/crypto-tracker       │
│   $ git clone repo .                    │
│   $ sudo docker-compose up -d           │
└─────────────────────────────────────────┘
              │
              │ Docker startup
              ▼
┌─────────────────────────────────────────┐
│   UGREEN NAS Docker Container           │
│   Running Crypto Tracker                │
│   Access @ https://nas-ip:5000          │
└─────────────────────────────────────────┘
```

### Synology DSM (Container Manager UI)

```
┌─────────────────────────────────────────┐
│   Your Computer                         │
└─────────────────────────────────────────┘
              │
              │ Browser / File Station
              ▼
┌─────────────────────────────────────────┐
│   Synology DSM Web Interface            │
│   • Install Docker (Package Center)     │
│   • Upload docker-compose.yml           │
└─────────────────────────────────────────┘
              │
              │ Container Manager
              ▼
┌─────────────────────────────────────────┐
│   Synology Container Manager            │
│   • Create from docker-compose.yml      │
│   • Configure volumes                   │
│   • Start container                     │
└─────────────────────────────────────────┘
              │
              │ Auto-deploy
              ▼
┌─────────────────────────────────────────┐
│   Synology Docker Container             │
│   Running Crypto Tracker                │
│   Access @ https://nas-ip:5000          │
└─────────────────────────────────────────┘
```

## Data Flow Architecture

```
                    ┌─────────────────┐
                    │   User Browser  │
                    │ https://nas:5000│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Flask Web UI   │
                    │  (HTTPS/SSL)    │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Config  │         │Database │         │ Reports │
   │ Engine  │         │ (SQLite)│         │ Export  │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        └───────────┬───────┴───────┬───────────┘
                    │               │
        ┌───────────▼───────────┐   │
        │  Persistent Volumes   │   │
        │                       │   │
        │ • configs/            │   │
        │ • inputs/             │   │
        │ • outputs/            │   │
        │ • processed_archive/  │   │
        │ • certs/              │   │
        └───────────────────────┘   │
                                    │
                    ┌───────────────▼───────────────┐
                    │ NAS Storage System            │
                    │ (Persistent & Backed Up)      │
                    └───────────────────────────────┘
```

## Resource Allocation

```
┌──────────────────────────────────┐
│     NAS Total Resources          │
│  (Example: 8GB RAM, 4-core CPU)  │
└──────────────────────────────────┘
        │
        ├─ Host OS (2GB RAM, 1-2 cores)
        │
        ├─ Docker Daemon (512MB RAM, <0.5 core)
        │
        ├─ Crypto Tracker Container ◄─ CONFIGURABLE
        │  ├─ Limit: 2GB RAM
        │  ├─ Limit: 2.0 CPU cores
        │  ├─ Reservation: 512MB RAM
        │  └─ Reservation: 0.5 CPU cores
        │
        └─ Other Services (~3GB RAM, ~0.5 cores)

Recommendations:
• Low-end NAS:     1GB RAM, 1 CPU limit
• Mid-range NAS:   2GB RAM, 2 CPU limit  (default)
• High-end NAS:    4-8GB RAM, 4+ CPU limit
```

## Health Check Mechanism

```
Docker Engine
    │
    └─ Every 30 seconds
       │
       ├─ Check: curl -f -k https://localhost:5000/health
       │
       ▼
    [Response 200 OK? ✓]
       │
       ├─ YES → Container healthy ✓
       │        (reset retries counter)
       │
       └─ NO → Failed attempt (counter++)
              │
              ├─ After 3 failures → Container marked unhealthy ⚠️
              │
              └─ After continued failures → Auto-restart ↻
                 (unless-stopped policy)
```

## Security Layers

```
                     Internet (DO NOT EXPOSE)
                            ↓ (Should be blocked)
┌────────────────────────────────────────────┐
│         NAS Firewall                       │
│  Allow: 5000 from trusted IPs only         │
└────────────────────────────────────────────┘
                            ↓ (Allowed from LAN)
┌────────────────────────────────────────────┐
│      HTTPS/TLS Layer                       │
│  • Self-signed certificate                 │
│  • Browser SSL verification                │
└────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────┐
│    Flask Application Layer                 │
│  • Session authentication                  │
│  • CSRF token protection                   │
│  • Request rate limiting                   │
│  • Input validation                        │
└────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────┐
│    Container Security Context              │
│  • Non-root user (UID 1000)                │
│  • No new privileges (no_new_privileges)   │
│  • Capability restrictions                 │
│  • Read-only root filesystem (optional)    │
└────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────┐
│    Data Encryption at Rest                 │
│  • Encrypted API keys (configs/)           │
│  • Encrypted wallet data (configs/)        │
│  • Database with encryption (optional)     │
└────────────────────────────────────────────┘
```

## Supported NAS Platforms Matrix

```
┌─────────────────────────────────────────────────────┐
│              SUPPORTED PLATFORMS                     │
└─────────────────────────────────────────────────────┘

Architecture:       ARM64          x86_64
                  (aarch64)      (AMD64)
                     │              │
        ┌────────────┴────────┐     │
        │                     │     │
    ┌───▼────────┐      ┌─────▼─────────────┐
    │  ARM NAS   │      │   x86 NAS         │
    │            │      │                   │
    │ Synology   │      │ Synology DS920+   │
    │  DS220+    │      │ Synology DS1019+  │
    │  DS920+    │      │                   │
    │  DS1520+   │      │ QNAP TS-453D      │
    │  DS1621+   │      │ QNAP TS-653D      │
    │            │      │                   │
    │ QNAP (some)│      │ Asustor Locker    │
    │            │      │ UGREEN NASync   ⭐│
    │ Raspi 4/5  │      │ UGREEN DXN      ⭐│
    │            │      │                   │
    │ Apple M1/2 │      │ Docker Desktop    │
    └────────────┘      │ Linux Servers     │
                        └───────────────────┘
```

---

This architecture ensures:
✅ Multi-platform support (ARM + x86)
✅ Data persistence and backup
✅ Security through isolation and limiting
✅ Automatic health monitoring and recovery
✅ Easy deployment on multiple NAS platforms
✅ Resource-aware to protect the host system
