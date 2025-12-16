#!/usr/bin/env python3
"""
================================================================================
WEB UI LAUNCHER - Start Web Interface Server
================================================================================

Convenience launcher for the web-based UI server.

Features:
    - Starts Flask development server with HTTPS support
    - Automatic certificate generation for local SSL
    - Browser auto-launch to web interface
    - Graceful shutdown handling

The web UI provides:
    - Authenticated access to all tax engine features
    - Interactive file upload and management
    - Real-time calculation progress tracking
    - Report viewing and download
    - Configuration management

Usage:
    python start_web_ui.py

Access at: https://localhost:5000
Default credentials are set during first-time setup.

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Start the web server"""
    web_server = Path(__file__).parent / 'src' / 'web' / 'server.py'
    
    print("Starting Crypto Tax Generator Web UI...")
    print("=" * 60)
    
    try:
        subprocess.run([sys.executable, str(web_server)])
    except KeyboardInterrupt:
        print("\n\nShutting down web server...")
    except Exception as e:
        print(f"\nError starting web server: {e}")
        print("\nTry running directly: python3 web_server.py")
        sys.exit(1)

if __name__ == '__main__':
    main()
