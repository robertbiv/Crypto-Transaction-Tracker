# Docker Deployment Guide for NAS

This guide covers deploying the Crypto Transaction Tracker on NAS devices using Docker, with support for both ARM-based (ARM64/aarch64) and x86-based (AMD64/x86_64) architectures.

## Supported Platforms

- **ARM64/aarch64**: Synology DS220+, DS920+, QNAP TS-x53D series, Raspberry Pi 4/5
- **AMD64/x86_64**: Most Intel/AMD-based NAS devices (Synology, QNAP, Asustor, etc.)

## Quick Start

### Option 1: Using Docker Compose (Recommended)

1. **Clone or copy the project to your NAS**
   ```bash
   cd /volume1/docker/crypto-tracker  # Adjust path for your NAS
   ```

2. **Start the container**
   ```bash
   docker-compose up -d
   ```

3. **Access the web UI**
   - Open your browser to: `https://YOUR_NAS_IP:5000`
   - Accept the self-signed certificate warning

### Option 2: Manual Docker Run

```bash
docker run -d \
  --name crypto-tracker \
  -p 5000:5000 \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/inputs:/app/inputs \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/processed_archive:/app/processed_archive \
  -v $(pwd)/certs:/app/certs \
  --restart unless-stopped \
  crypto-tracker:latest
```

## Building Multi-Architecture Images

### Prerequisites

- Docker with BuildKit enabled (Docker 19.03+)
- `docker buildx` plugin installed

### Building on Windows

```powershell
.\build-multiarch.ps1 latest
```

### Building on Linux/Mac

```bash
chmod +x build-multiarch.sh
./build-multiarch.sh latest
```

### Manual Multi-Arch Build

```bash
# Create builder instance
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap

# Build for both platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag crypto-tracker:latest \
  --load \
  .
```

## NAS-Specific Setup Guides

### Synology NAS

1. **Install Docker** (via Package Center)
2. **SSH into your NAS** or use File Station
3. **Create project directory**:
   ```bash
   mkdir -p /volume1/docker/crypto-tracker
   cd /volume1/docker/crypto-tracker
   ```
4. **Upload files** (via File Station or SCP):
   - `Dockerfile`
   - `docker-compose.yml`
   - All application files
   
5. **Build and run**:
   ```bash
   sudo docker-compose up -d
   ```

6. **Access via DSM**:
   - Container Manager → Container → crypto-transaction-tracker
   - Click "Details" to view logs
   - Use "Stop/Start" to manage the container

### QNAP NAS (Container Station)

1. **Install Container Station** (via App Center)
2. **Create Container**:
   - Open Container Station
   - Click "Create" → "Create Application"
   - Upload `docker-compose.yml`
   - Click "Create"

3. **Access**:
   - Container Station → Containers → crypto-transaction-tracker
   - View logs, start/stop as needed

### Asustor NAS (Docker CE)

1. **Install Docker CE** (via App Central)
2. **Use Terminal** or SSH:
   ```bash
   cd /volume1/docker
   git clone <your-repo> crypto-tracker
   cd crypto-tracker
   docker-compose up -d
   ```

### UGREEN NAS (NASync/DXN Series)

UGREEN NAS devices run a custom Linux OS with Docker support. Here's how to deploy:

1. **Enable SSH**:
   - Open UGREEN's web interface (typically http://nas-ip:8001)
   - Settings → System → SSH → Enable SSH
   - Note the port number (usually 22 or 2222)

2. **SSH into your UGREEN NAS**:
   ```bash
   # Default credentials: admin/admin (change these!)
   ssh -p 22 admin@your-nas-ip
   # or
   ssh -p 2222 admin@your-nas-ip
   ```

3. **Create project directory**:
   ```bash
   # UGREEN uses /mnt for volumes
   mkdir -p /mnt/docker/crypto-tracker
   cd /mnt/docker/crypto-tracker
   ```

4. **Download/copy files**:
   ```bash
   # Option A: Clone from Git
   git clone <your-repo> .
   
   # Option B: Upload via SCP
   # From your computer:
   scp -P 22 -r Dockerfile docker-compose.yml ... admin@your-nas-ip:/mnt/docker/crypto-tracker/
   ```

5. **Verify Docker is installed**:
   ```bash
   docker --version
   docker-compose --version
   
   # If not installed, try:
   sudo apt-get update
   sudo apt-get install docker.io docker-compose
   sudo usermod -aG docker admin
   ```

6. **Build and run**:
   ```bash
   sudo docker-compose up -d
   ```

7. **Verify it's running**:
   ```bash
   sudo docker ps
   sudo docker-compose logs
   ```

8. **Access via web**:
   - Open browser to: `https://your-nas-ip:5000`
   - Complete first-time setup

9. **Make it persistent** (auto-restart on reboot):
   ```bash
   # Check if container persists
   sudo docker-compose ps
   
   # Add to crontab for auto-startup on reboot (optional)
   sudo crontab -e
   # Add this line:
   # @reboot cd /mnt/docker/crypto-tracker && docker-compose up -d
   ```

**UGREEN NAS Specifics:**
- Storage paths: `/mnt/` instead of `/volume1/`
- SSH port may be 2222 instead of 22
- Web interface usually on port 8001
- Use `sudo` for Docker commands
- No native container UI (use SSH/web UI only)

**Supported UGREEN Models:**
- NASync Duo Pro (x86)
- NASync Duo (x86)
- DXN5600/DXN5400 series
- Other DXN models with Docker support

## Configuration

### Volume Mappings

The following directories should be mapped as volumes for persistence:

| Container Path | Description | Recommended Host Path |
|---------------|-------------|----------------------|
| `/app/configs` | Configuration files | `./configs` |
| `/app/inputs` | Input CSV/Excel files | `./inputs` |
| `/app/outputs` | Reports and logs | `./outputs` |
| `/app/processed_archive` | Processed files | `./processed_archive` |
| `/app/certs` | SSL certificates | `./certs` |

### Environment Variables

You can customize behavior via environment variables in `docker-compose.yml`:

```yaml
environment:
  - TZ=America/New_York  # Set your timezone
  - FLASK_ENV=production
  - LOG_LEVEL=INFO
```

### Resource Limits

Adjust resource limits based on your NAS capabilities:

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # Increase for more processing power
      memory: 4G       # Increase for larger datasets
    reservations:
      cpus: '1.0'
      memory: 1G
```

## Networking

### Port Configuration

Default port: `5000`

To change the port, edit `docker-compose.yml`:

```yaml
ports:
  - "8443:5000"  # Access via https://nas-ip:8443
```

### Reverse Proxy Setup

For use with Nginx Proxy Manager or Traefik on your NAS:

```yaml
# Add to docker-compose.yml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.crypto-tracker.rule=Host(`crypto.yourdomain.com`)"
  - "traefik.http.services.crypto-tracker.loadbalancer.server.port=5000"
```

## Security

### SSL/TLS Certificates

The application generates self-signed certificates on first run. For production:

1. **Use Let's Encrypt** (if NAS is internet-accessible):
   ```yaml
   volumes:
     - /volume1/docker/letsencrypt/certs:/app/certs:ro
   ```

2. **Use NAS certificates**:
   - Synology: Copy from `/usr/syno/etc/certificate/`
   - QNAP: Copy from `/etc/config/apache/ssl.crt/`

### Firewall Rules

Ensure port 5000 (or your custom port) is accessible:
- Synology: Control Panel → Security → Firewall
- QNAP: Network & File Services → Security → Firewall

## Maintenance

### View Logs

```bash
docker-compose logs -f
# or
docker logs -f crypto-transaction-tracker
```

### Update Container

```bash
docker-compose pull
docker-compose up -d
```

### Backup Data

```bash
# Backup volumes
tar -czf crypto-tracker-backup-$(date +%Y%m%d).tar.gz \
  configs/ inputs/ outputs/ processed_archive/
```

### Restart Container

```bash
docker-compose restart
# or
docker restart crypto-transaction-tracker
```

## Troubleshooting

### Container Won't Start

1. Check logs: `docker-compose logs`
2. Verify permissions: `ls -la` on volume directories
3. Check port conflicts: `netstat -tulpn | grep 5000`

### Can't Access Web UI

1. Verify container is running: `docker ps`
2. Check firewall rules on NAS
3. Try accessing via IP: `https://192.168.x.x:5000`
4. Check health status: `docker inspect crypto-transaction-tracker | grep Health`

### Performance Issues

1. Increase resource limits in `docker-compose.yml`
2. Check NAS resource usage (CPU, RAM, Disk I/O)
3. Reduce concurrent processing if needed

### Architecture Mismatch

If you get "exec format error":
```bash
# Verify your platform
docker version | grep "OS/Arch"

# Rebuild for correct architecture
docker buildx build --platform linux/arm64 -t crypto-tracker:latest .
# or
docker buildx build --platform linux/amd64 -t crypto-tracker:latest .
```

## Advanced Configuration

### Running CLI Commands

```bash
# Execute commands inside the container
docker exec -it crypto-transaction-tracker python cli.py --help

# Process a file
docker exec -it crypto-transaction-tracker \
  python cli.py process --input /app/inputs/transactions.csv
```

### Custom Python Scripts

Mount your scripts directory:

```yaml
volumes:
  - ./custom_scripts:/app/custom_scripts
```

Then run:
```bash
docker exec -it crypto-transaction-tracker \
  python /app/custom_scripts/my_script.py
```

## Support

For issues or questions:
1. Check the logs first
2. Review this documentation
3. Check the main README.md
4. Submit an issue on GitHub

## Performance Recommendations

- **ARM NAS**: Expect 50-70% of x86 performance
- **RAM**: Minimum 2GB, recommend 4GB for large datasets
- **Storage**: SSD recommended for database and outputs
- **CPU**: 2+ cores recommended for parallel processing

## Example NAS Configurations

### Budget ARM NAS (2GB RAM)
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1536M
```

### Mid-Range x86 NAS (8GB RAM)
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
```

### High-End NAS (16GB+ RAM)
```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 8G
```
