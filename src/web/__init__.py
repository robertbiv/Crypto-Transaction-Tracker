"""
================================================================================
WEB MODULE - Web Interface and Scheduling
================================================================================

Web-based user interface with authentication and automated scheduling.

Components:
    server.py - Flask web server with HTTPS and authentication
    scheduler.py - Background task scheduler for automated runs

Note:
    Server is imported directly by start_web_ui.py launcher.
    No exports in __init__.py to avoid circular import issues.

Usage:
    python start_web_ui.py
    python src/web/server.py

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

# Web server is imported directly by start_web_ui.py
# No need to expose in __init__.py to avoid circular imports

__all__ = []
