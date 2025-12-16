"""
================================================================================
TOOLS MODULE - Command-Line Utilities
================================================================================

User-facing CLI tools for setup, configuration, and maintenance.

Available Tools:
    setup.py - First-time configuration wizard
    review_fixer.py - Interactive issue remediation tool

Usage:
    python src/tools/setup.py
    python src/tools/review_fixer.py
    
    Or via CLI wrapper:
    python cli.py setup
    python cli.py fix-review

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

# Import modules but don't expose everything to avoid circular imports
from src.tools import setup
from src.tools import review_fixer

__all__ = ['setup', 'review_fixer']
