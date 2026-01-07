# NAS Deployment Guide

Deploy Crypto Transaction Tracker to your NAS using Docker. Choose your platform below.

## Quick Start

```yaml
# docker-compose.yml for any NAS with Docker
version: '3.8'
services:
  crypto-tracker:
    image: robertbiv/crypto-tracker:latest
    container_name: crypto-transaction-tracker
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./crypto-configs:/app/configs
      - ./crypto-inputs:/app/inputs
      - ./crypto-outputs:/app/outputs
      - ./crypto-archive:/app/processed_archive
      - ./crypto-certs:/app/certs
    environment:
      - TZ=UTC
      - PYTHONUNBUFFERED=1
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

## Platform-Specific Instructions

### UGREEN NAS (GUI-Based)

**Setup Time:** ~15 minutes | **SSH Required:** No

1. Open UGREEN web interface → Docker section
2. Click "Create from Compose"
3. Paste the docker-compose YAML above
4. Configure:
   - **Image name:** `robertbiv/crypto-tracker:latest`
   - **Port mapping:** 5000 → 5000
   - **Volume mounts:** Create directories for configs, inputs, outputs, archive, certs
   - **CPU/RAM limits:** 2 cores, 2GB memory
5. Click "Create"
6. Wait 2-3 minutes for image download
7. Access: `https://your-ugreen-ip:5000`

**Troubleshooting:**
- If port 5000 unavailable: Change to 5001 or 5002
- If image won't download: Check internet connection, try refreshing
- If stuck on startup: Check Docker logs in UGREEN interface

---

### Synology NAS

**Setup Time:** ~10 minutes | **SSH Required:** No (via GUI only)

#### Option A: Docker (GUI)
1. Open DSM → Package Center → Search "Docker" → Install
2. Open Docker app → Registry → Search "crypto-tracker"
3. Download `robertbiv/crypto-tracker:latest`
4. Click "Launch" → Configure container:
   - **Port settings:** Container 5000 → Local port 5000
   - **Volume settings:** Create 5 mount points for configs, inputs, outputs, archive, certs
   - **Resources:** Set CPU/memory limits
5. Create and start
6. Access: `https://synology-ip:5000`

#### Option B: Using docker-compose (SSH)
```bash
ssh admin@synology-ip
cd /volume1/docker
# Paste the docker-compose.yml above
docker-compose up -d
```

---

### QNAP NAS

**Setup Time:** ~10 minutes | **SSH Required:** No (via GUI)

1. Open QTS management → App Center → Search "Docker" → Install
2. Open Container Station
3. Images → Search → Enter `robertbiv/crypto-tracker:latest`
4. Download image
5. Containers → Create new:
   - **Image:** crypto-tracker:latest
   - **Port mapping:** 5000 → 5000
   - **Storage:** Map 5 volumes to network shares
   - **Resources:** Set CPU/memory limits
6. Apply and run
7. Access: `https://qnap-ip:5000`

---

### Generic Docker Compose (Any NAS with Docker)

**Setup Time:** ~5 minutes | **SSH Required:** Yes

```bash
# SSH into your NAS
ssh user@nas-ip

# Create project directory
mkdir -p ~/crypto-tracker
cd ~/crypto-tracker

# Create docker-compose.yml with the config above
nano docker-compose.yml
# Paste the YAML, save (Ctrl+X, Y, Enter)

# Start the container
docker-compose up -d

# Verify it's running
docker-compose ps

# View logs if needed
docker-compose logs crypto-tracker
```

Access: `https://nas-ip:5000`

---

## Docker Hub Setup (For Maintainers)

Want automatic builds when you push code?

### Prerequisites
- Docker Hub account (free at docker.com)
- GitHub repository with this code

### Steps

**1. Docker Hub Access Token**
- hub.docker.com → Account Settings → Security → New Access Token
- Name: `github-crypto-tracker`
- Permissions: Read & Write
- Copy the token

**2. GitHub Secrets** (in your repository)
- Settings → Secrets and variables → Actions
- Add `DOCKERHUB_USERNAME`: your Docker Hub username
- Add `DOCKERHUB_TOKEN`: the token from step 1

**3. Trigger**
- Push code to GitHub or create a tag (e.g., `v1.0.0`)
- Workflow automatically builds for ARM64 and x86_64
- Check Actions tab to monitor
- Image appears in Docker Hub after ~10-15 minutes

**Verify:** hub.docker.com → Your repo → Tags (should see `latest` and version tags)

---

## Data Persistence

All NAS platforms store data in mapped volumes:
- `crypto-configs/` - Configuration files
- `crypto-inputs/` - Transaction files
- `crypto-outputs/` - Generated reports
- `crypto-archive/` - Processed transactions
- `crypto-certs/` - SSL certificates

**Backup:** Copy these directories to your computer monthly

---

## Performance Tuning

### Recommended Settings
- **CPU:** 2-4 cores (adjust based on NAS)
- **RAM:** 2-4GB (adjust based on NAS)
- **Disk:** 10GB minimum free space

### Reduce Resource Usage
Lower CPU/RAM limits if your NAS is slow:
```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'      # Reduce to 1 core
      memory: 1G       # Reduce to 1GB
```

---

## Accessing Your Instance

1. **Initial setup:** `https://your-nas-ip:5000`
2. **Accept SSL warning** (self-signed certificate is normal)
3. **Create admin account** on first visit
4. **Start uploading transactions**

## Common Issues

| Issue | Solution |
|-------|----------|
| **Port already in use** | Change 5000 to 5001, 5002, etc. in docker-compose |
| **Image won't download** | Check internet connection; try again after 5 minutes |
| **Container won't start** | Check Docker logs in NAS interface |
| **Can't access from browser** | Verify container is running; check firewall; try IP address |
| **SSL certificate warning** | Normal - accept/bypass warning to continue |

---

## Support

- Check Docker logs in your NAS interface
- Verify port mapping is correct
- Ensure volumes have read/write permissions
- Check available disk space on NAS
