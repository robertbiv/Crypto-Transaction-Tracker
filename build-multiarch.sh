#!/bin/bash
#
# Multi-Architecture Docker Build Script
# Builds for both ARM64 (aarch64) and AMD64 (x86_64) platforms
#
# Requirements:
#   - Docker with BuildKit enabled
#   - docker buildx installed
#
# Usage:
#   ./build-multiarch.sh [tag]
#   
# Example:
#   ./build-multiarch.sh latest
#   ./build-multiarch.sh v1.0.0

set -e

# Configuration
IMAGE_NAME="crypto-tracker"
TAG="${1:-latest}"
PLATFORMS="linux/amd64,linux/arm64"

echo "=========================================="
echo "Multi-Architecture Docker Build"
echo "=========================================="
echo "Image: ${IMAGE_NAME}:${TAG}"
echo "Platforms: ${PLATFORMS}"
echo "=========================================="

# Check if buildx is available
if ! docker buildx version &> /dev/null; then
    echo "Error: docker buildx is not installed!"
    echo "Please install it: https://docs.docker.com/buildx/working-with-buildx/"
    exit 1
fi

# Create a new builder instance if it doesn't exist
if ! docker buildx inspect multiarch-builder &> /dev/null; then
    echo "Creating new buildx builder instance..."
    docker buildx create --name multiarch-builder --use
    docker buildx inspect --bootstrap
else
    echo "Using existing buildx builder instance..."
    docker buildx use multiarch-builder
fi

# Build and push for multiple architectures
echo "Building for platforms: ${PLATFORMS}"
docker buildx build \
    --platform "${PLATFORMS}" \
    --tag "${IMAGE_NAME}:${TAG}" \
    --load \
    --progress=plain \
    .

echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo "Image: ${IMAGE_NAME}:${TAG}"
echo ""
echo "To run the container:"
echo "  docker-compose up -d"
echo ""
echo "Or manually:"
echo "  docker run -d -p 5000:5000 -v \$(pwd)/outputs:/app/outputs ${IMAGE_NAME}:${TAG}"
echo "=========================================="
