# Docker Hub Publishing Setup Guide

This guide explains how to set up automated multi-architecture Docker image builds and publishing to Docker Hub.

## Prerequisites

1. **GitHub Account** with this repository
2. **Docker Hub Account** (free at https://hub.docker.com)
3. **GitHub Actions** enabled (default for public repos)

## Step 1: Create Docker Hub Account

1. Go to https://hub.docker.com
2. Click "Sign Up"
3. Create account with:
   - Email address
   - Username (e.g., `yourname`)
   - Password (strong, 12+ characters)
4. Verify email

## Step 2: Create Docker Hub Personal Access Token

1. Log in to Docker Hub
2. Go to **Account Settings** → **Security**
3. Click **"New Access Token"**
4. Set **Token Description**: `GitHub Actions Crypto Tracker`
5. Click **"Generate"**
6. Copy the token (you'll need it in Step 3)

## Step 3: Add Secrets to GitHub

1. Go to your GitHub repository
2. Navigate to: **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add two secrets:

   **First Secret:**
   - Name: `DOCKERHUB_USERNAME`
   - Value: Your Docker Hub username

   **Second Secret:**
   - Name: `DOCKERHUB_TOKEN`
   - Value: Your Docker Hub access token (from Step 2)

5. Click **"Add secret"** for each

## Step 4: Verify GitHub Actions Workflow

1. Go to your GitHub repository
2. Click **"Actions"** tab
3. You should see the workflow: **"Build and Push Multi-Arch Docker Image"**
4. If not visible, check that `.github/workflows/build-multiarch-docker.yml` exists

## Step 5: Trigger First Build

### Option A: Via Git Push to Main Branch

```bash
# Make a small change to main branch
git add .
git commit -m "Trigger Docker build"
git push origin main

# Go to GitHub Actions to watch the build
```

### Option B: Via Git Tag (Version Release)

```bash
# Tag a release
git tag v1.0.0
git push origin v1.0.0

# Image will be tagged as:
# - yourname/crypto-tracker:1.0.0
# - yourname/crypto-tracker:1.0
# - yourname/crypto-tracker:latest
```

### Option C: Manual Trigger

1. Go to GitHub repository
2. Click **"Actions"** tab
3. Select **"Build and Push Multi-Arch Docker Image"**
4. Click **"Run workflow"** button
5. Click **"Run workflow"** in the popup

## Step 6: Monitor the Build

1. Go to **Actions** tab in GitHub
2. Click the running workflow
3. Watch the build progress:
   - "Checkout repository"
   - "Set up QEMU" (ARM support)
   - "Set up Docker Buildx"
   - "Log in to Docker Hub"
   - "Build and push Docker image"

4. Build typically takes **10-15 minutes** for both architectures

## Step 7: Verify in Docker Hub

1. Log in to Docker Hub
2. Go to **Repositories**
3. You should see: `yourname/crypto-tracker`
4. Click on it to see:
   - **Tags** (latest, version numbers, etc.)
   - **Platforms** (linux/amd64, linux/arm64)
   - **Build history**

## Step 8: Use in UGREEN NAS

Once published to Docker Hub, you can use it in UGREEN:

1. In UGREEN Docker interface
2. Use image: `yourname/crypto-tracker:latest`
3. UGREEN will automatically pull the correct architecture

## Continuous Integration

Now that it's set up, builds happen automatically:

### Trigger Events

Builds are triggered when you:
- ✅ Push to `main` branch
- ✅ Push to `develop` branch
- ✅ Create a version tag (v1.0.0, v1.0.1, etc.)
- ✅ Manually trigger via Actions UI

### Automatic Tagging

Images are tagged as:
- `latest` - Always points to main branch latest
- `v1.0.0` - Specific version from tags
- `develop` - Latest from develop branch
- `main` - Latest from main branch

## Using Official Organization (Optional)

If you want a cleaner name without username:

1. Create a Docker Hub Organization (paid feature)
2. Add GitHub App integration
3. Update workflow to use org name
4. Images would be: `organization/crypto-tracker`

## Troubleshooting

### Build Fails with "Authentication Failed"

**Solution:**
1. Verify secrets are set correctly
2. Check Docker Hub token isn't expired
3. Regenerate token and update GitHub secret

### "No such file or directory: Dockerfile"

**Solution:**
1. Ensure `Dockerfile` exists in repository root
2. Check `.github/workflows/build-multiarch-docker.yml` path is correct

### Build Takes Too Long

**Normal:** First build can take 15-20 minutes (both architectures)
**Subsequent:** Usually 5-10 minutes (cached layers)

### Images Not Appearing on Docker Hub

**Check:**
1. Build logs for errors (Actions tab)
2. Secrets are correctly set
3. Token hasn't expired
4. Repository name matches workflow

## UGREEN NAS Deployment with Docker Hub

Once your image is on Docker Hub, UGREEN users can deploy simply:

1. Open UGREEN Docker interface
2. Create container from: `yourname/crypto-tracker:latest`
3. Configure volumes and ports
4. Deploy - UGREEN automatically pulls the ARM-compatible image

**No build needed on UGREEN!** The image is ready to use.

## Example docker-compose for UGREEN

Users would use:

```yaml
version: '3.8'
services:
  crypto-tracker:
    image: yourname/crypto-tracker:latest  # Pre-built from Docker Hub
    container_name: crypto-transaction-tracker
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./configs:/app/configs
      - ./inputs:/app/inputs
      - ./outputs:/app/outputs
```

## Next Steps

1. ✅ Complete steps 1-3 above
2. ✅ Verify workflow file exists
3. ✅ Push code to trigger first build
4. ✅ Monitor in Actions tab
5. ✅ Verify image appears on Docker Hub
6. ✅ Share image URL with UGREEN users

## Support Commands

```bash
# Check Docker Hub for your images
docker search yourname/crypto-tracker

# Pull the image locally to test
docker pull yourname/crypto-tracker:latest

# Run it locally
docker-compose -f docker-compose.yml up -d

# Check what's on Docker Hub via CLI
curl https://registry.hub.docker.com/v2/repositories/yourname/crypto-tracker/
```

## Useful Links

- Docker Hub: https://hub.docker.com
- Docker Hub Docs: https://docs.docker.com/docker-hub/
- GitHub Actions: https://github.com/features/actions
- QEMU (ARM emulation): https://github.com/docker/setup-qemu-action

---

Once set up, your multi-architecture images are automatically built and ready for UGREEN NAS users to deploy! 🚀
