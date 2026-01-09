#!/bin/bash
set -e

# Docker entrypoint script for Crypto Transaction Tracker
# Ensures proper directory permissions when using volume mounts

echo "Initializing Crypto Transaction Tracker..."

# Directories that need to be writable
REQUIRED_DIRS=(
    "/app/inputs"
    "/app/outputs"
    "/app/outputs/logs"
    "/app/processed_archive"
    "/app/configs"
    "/app/certs"
)

# Create directories if they don't exist and ensure they're writable
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir" 2>/dev/null || true
    fi
    
    # Try to write a test file to check permissions
    if ! touch "$dir/.write_test" 2>/dev/null; then
        echo "WARNING: Cannot write to $dir - attempting to fix permissions..."
        # This will only work if running as root or with proper capabilities
        chmod -R 755 "$dir" 2>/dev/null || true
    else
        rm -f "$dir/.write_test"
    fi
done

# Initialize config.json if it doesn't exist
if [ ! -f "/app/configs/config.json" ]; then
    echo "Initializing default configuration..."
    cat > /app/configs/config.json <<'EOF'
{
  "transaction_calculation": {
    "method": "FIFO",
    "cost_basis_method": "FIFO"
  },
  "ml_fallback": {
    "enabled": false,
    "model_name": "shim",
    "confidence_threshold": 0.85
  },
  "accuracy_mode": {
    "enabled": false,
    "fraud_detection": false,
    "smart_descriptions": false,
    "pattern_learning": false,
    "natural_language_search": false
  },
  "anomaly_detection": {
    "price_error_threshold": 20,
    "extreme_value_threshold": 3.0,
    "dust_threshold_usd": 0.10
  }
}
EOF
fi

echo "Directory initialization complete."
echo "Starting application..."

# Execute the main command (passed as arguments to this script)
exec "$@"
