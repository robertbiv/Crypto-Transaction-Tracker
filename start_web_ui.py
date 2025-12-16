#!/usr/bin/env python3
"""
Start the Crypto Tax Generator Web UI Server
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
