#
# Multi-Architecture Docker Build Script (PowerShell)
# Builds for both ARM64 (aarch64) and AMD64 (x86_64) platforms
#
# Requirements:
#   - Docker Desktop with BuildKit enabled
#   - docker buildx installed
#
# Usage:
#   .\build-multiarch.ps1 [tag]
#   
# Example:
#   .\build-multiarch.ps1 latest
#   .\build-multiarch.ps1 v1.0.0

param(
    [string]$Tag = "latest"
)

# Configuration
$ImageName = "crypto-tracker"
$Platforms = "linux/amd64,linux/arm64"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Multi-Architecture Docker Build" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Image: ${ImageName}:${Tag}"
Write-Host "Platforms: ${Platforms}"
Write-Host "==========================================" -ForegroundColor Cyan

# Check if buildx is available
try {
    docker buildx version | Out-Null
} catch {
    Write-Host "Error: docker buildx is not installed!" -ForegroundColor Red
    Write-Host "Please install it: https://docs.docker.com/buildx/working-with-buildx/"
    exit 1
}

# Create a new builder instance if it doesn't exist
$builderExists = docker buildx inspect multiarch-builder 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating new buildx builder instance..." -ForegroundColor Yellow
    docker buildx create --name multiarch-builder --use
    docker buildx inspect --bootstrap
} else {
    Write-Host "Using existing buildx builder instance..." -ForegroundColor Green
    docker buildx use multiarch-builder
}

# Build and push for multiple architectures
Write-Host "Building for platforms: ${Platforms}" -ForegroundColor Yellow
docker buildx build `
    --platform $Platforms `
    --tag "${ImageName}:${Tag}" `
    --load `
    --progress=plain `
    .

if ($LASTEXITCODE -eq 0) {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "Build complete!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "Image: ${ImageName}:${Tag}"
    Write-Host ""
    Write-Host "To run the container:" -ForegroundColor Cyan
    Write-Host "  docker-compose up -d"
    Write-Host ""
    Write-Host "Or manually:" -ForegroundColor Cyan
    Write-Host "  docker run -d -p 5000:5000 -v `$(pwd)/outputs:/app/outputs ${ImageName}:${Tag}"
    Write-Host "==========================================" -ForegroundColor Green
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
