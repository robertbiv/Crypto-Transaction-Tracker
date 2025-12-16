"""
================================================================================
SRC PACKAGE - Modular Source Code Organization
================================================================================

Top-level package containing all application modules organized by function.

Package Structure:
    src/core/      - Core business logic (engine, database, encryption)
    src/tools/     - User-facing CLI tools (setup, review_fixer)
    src/utils/     - Shared utilities (logging, config, constants)
    src/web/       - Web UI server and scheduler

Design Principles:
    - Separation of concerns
    - Minimal circular dependencies
    - Test-friendly architecture
    - Clear public APIs

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

__version__ = "2025.1"
__author__ = "robertbiv"
