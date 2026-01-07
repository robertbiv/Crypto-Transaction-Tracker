# Multi-architecture Dockerfile for Crypto Transaction Tracker
# Supports both ARM64 (aarch64) and AMD64 (x86_64) for NAS deployment

FROM python:3.11-slim

# Set build arguments for cross-platform support
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Metadata
LABEL maintainer="robertbiv"
LABEL description="Crypto Transaction Tracker - Multi-architecture NAS deployment"
LABEL version="1.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
# These are minimal and work on both ARM and x86
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt requirements-ml.txt ./

# Install Python dependencies
# Install main requirements first
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Install ML requirements (optional, larger packages)
# Install with --no-deps to avoid conflicts, then install missing deps
RUN pip install -r requirements-ml.txt || \
    echo "Some ML packages may have failed, continuing..."

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/inputs \
    /app/outputs \
    /app/outputs/logs \
    /app/processed_archive \
    /app/configs \
    /app/certs \
    /app/web_static \
    /app/web_templates && \
    chmod -R 755 /app

# Create a non-root user for security
RUN useradd -m -u 1000 cryptotracker && \
    chown -R cryptotracker:cryptotracker /app

# Switch to non-root user
USER cryptotracker

# Expose port for web UI
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f -k https://localhost:5000/health || exit 1

# Default command - run web UI
CMD ["python", "start_web_ui.py"]
