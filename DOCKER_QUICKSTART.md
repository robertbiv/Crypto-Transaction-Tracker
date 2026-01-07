# Docker Quick Start Guide

## TL;DR - Get Started in 5 Minutes

### 1. Build the Image

**On Windows:**
```powershell
.\build-multiarch.ps1 latest
```

**On Linux/Mac/NAS SSH:**
```bash
chmod +x build-multiarch.sh
./build-multiarch.sh latest
```

### 2. Start the Container

```bash
docker-compose up -d
```

### 3. Access the Web UI

Open your browser to: **https://YOUR_IP:5000**

- Accept the self-signed SSL certificate warning
- Complete first-time setup
- Start tracking your crypto transactions!

## What You Get

✅ **Multi-architecture support** - Works on ARM and x86 NAS devices  
✅ **Persistent storage** - All data saved to volumes  
✅ **Automatic SSL** - Self-signed certificates generated on first run  
✅ **Resource limits** - CPU and memory constraints to protect your NAS  
✅ **Health checks** - Automatic container monitoring  
✅ **Automatic restart** - Container restarts if it crashes  

## Files Created

The Docker setup creates these files:

```
Crypto-Transaction-Tracker/
├── Dockerfile              # Multi-arch container definition
├── docker-compose.yml      # Easy deployment configuration
├── .dockerignore          # Optimized build context
├── build-multiarch.sh     # Linux/Mac build script
├── build-multiarch.ps1    # Windows build script
├── DOCKER.md              # Full documentation
├── DOCKER_QUICKSTART.md   # This file
└── DOCKER_SETUP_SUMMARY.md # Technical details
```

## NAS-Specific Quick Links

- **Synology DSM**: See "DOCKER.md" → "Synology NAS" section
- **QNAP**: See "DOCKER.md" → "QNAP NAS" section
- **Asustor**: See "DOCKER.md" → "Asustor NAS" section
- **UGREEN NAS**: See "DOCKER.md" → "UGREEN NAS" section (SSH-based deployment)

## Common Commands

### View Logs
```bash
docker-compose logs -f
```

### Restart Container
```bash
docker-compose restart
```

### Stop Container
```bash
docker-compose down
```

### Update Container
```bash
docker-compose pull
docker-compose up -d
```

### Execute Commands Inside Container
```bash
# Run CLI
docker exec -it crypto-transaction-tracker python cli.py --help

# Process a file
docker exec -it crypto-transaction-tracker \
  python cli.py process --input /app/inputs/transactions.csv
```

## Volume Locations

Data is stored in these directories (relative to project root):

- **configs/** - Configuration files
- **inputs/** - CSV/Excel transaction files
- **outputs/** - Reports and logs
- **processed_archive/** - Archived processed files
- **certs/** - SSL certificates

All of these are **automatically persisted** even if you restart the container.

## Changing the Port

Edit `docker-compose.yml` and change:

```yaml
ports:
  - "8443:5000"  # Access via https://your-ip:8443
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

## Resource Management

Default limits (edit in `docker-compose.yml`):

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Max 2 CPU cores
      memory: 2G       # Max 2GB RAM
```

### Recommended Settings

**Low-end NAS (2-4GB RAM):**
```yaml
limits:
  cpus: '1.0'
  memory: 1G
```

**Mid-range NAS (8GB+ RAM):**
```yaml
limits:
  cpus: '4.0'
  memory: 4G
```

**High-end NAS (16GB+ RAM):**
```yaml
limits:
  cpus: '8.0'
  memory: 8G
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs

# Check if port is already in use
docker ps -a
netstat -an | findstr :5000  # Windows
netstat -an | grep :5000     # Linux
```

### Can't access web UI
1. Verify container is running: `docker ps`
2. Check your firewall
3. Try: `https://localhost:5000` from the NAS itself
4. Check health: `docker inspect crypto-transaction-tracker | grep Health`

### "exec format error"
Your architecture doesn't match. Rebuild for your platform:

```bash
# For ARM (Raspberry Pi, some NAS)
docker buildx build --platform linux/arm64 -t crypto-tracker:latest .

# For x86 (Most NAS)
docker buildx build --platform linux/amd64 -t crypto-tracker:latest .
```

### Out of memory
Reduce memory limits in `docker-compose.yml` or close other containers.

## NAS-Specific Notes

### Synology DSM 7.x
- Access via Container Manager
- Make sure Docker package is installed
- Use SSH or Task Scheduler for docker-compose commands

### QNAP
- Access via Container Station
- Upload docker-compose.yml via UI
- Or use SSH for command-line control

### Asustor
- Install Docker CE from App Central
- Use SSH for all commands

## Security Tips

1. **Change default credentials** on first login
2. **Use strong passwords** - at least 12 characters
3. **Restrict network access** - firewall rules to trusted IPs only
4. **Regular backups** - backup the volumes directory
5. **Update regularly** - rebuild images for security updates

## Backup Your Data

### Quick Backup
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz configs/ outputs/ processed_archive/
```

### Restore
```bash
tar -xzf backup-YYYYMMDD.tar.gz
docker-compose restart
```

## Next Steps

- Read [DOCKER.md](DOCKER.md) for complete documentation
- Check [README.md](README.md) for feature details
- Review [docs/](docs/) for advanced configuration

## Support

Having issues? Check:
1. Container logs: `docker-compose logs`
2. Health status: `curl -k https://localhost:5000/health`
3. Full docs: [DOCKER.md](DOCKER.md)

## Performance Tips

- Use SSD for the outputs/ directory if possible
- Increase CPU limits for faster processing
- Close unused containers to free resources
- Monitor resource usage via your NAS dashboard
