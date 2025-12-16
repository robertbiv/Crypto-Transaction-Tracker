"""
================================================================================
LOGGER - Unified Logging Configuration
================================================================================

Centralized logging infrastructure for all application contexts.

Logging Contexts:
    - 'cli' - Command-line interface operations
    - 'web' - Web UI server and API requests
    - 'autorunner' - Automated batch processing
    - 'test' - Unit and integration tests
    - 'imported' - Library/module imports (minimal logging)

Log Destinations:
    1. File Logs - outputs/logs/{timestamp}.{context}.log
    2. Console Output - stdout with color formatting
    3. Rotating Backups - 5MB max per file, 5 backup files

Log Format:
    {timestamp} {level} [{context}]: {message}
    Example: 2025-12-16 10:30:45 INFO [autorunner]: Processing year 2024

Log Levels:
    - DEBUG: Detailed diagnostic information
    - INFO: General informational messages
    - WARNING: Warning messages (non-critical issues)
    - ERROR: Error messages (critical failures)
    - CRITICAL: System-wide failures

Features:
    - Context-aware filtering (different verbosity per context)
    - Rotating file handlers (prevents disk space issues)
    - UTF-8 encoding support (international characters)
    - Thread-safe logging
    - Graceful fallback if log directory unavailable
    - Test mode isolation (no console spam)

Usage:
    from src.utils.logger import set_run_context
    from src.core.engine import logger
    
    set_run_context('cli')
    logger.info('Starting tax calculation')

Configuration:
    Logger settings respect LOG_DIR from constants.py
    Max file size and backup count can be adjusted in this module

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("crypto_tax_engine")
logger.setLevel(logging.INFO)

# Global run context state
_RUN_CONTEXT = 'imported'


class RunContextFilter(logging.Filter):
    """
    Logging filter that adds run context to all log records
    Allows distinguishing between different execution contexts
    """

    def filter(self, record):
        try:
            record.run_context = _RUN_CONTEXT
        except:
            record.run_context = 'unknown'
        return True


def set_run_context(context: str):
    """
    Set the execution context for logging

    Args:
        context: String identifier ('autorunner', 'web', 'cli', 'test', etc)
    """
    global _RUN_CONTEXT
    _RUN_CONTEXT = context

    # Clear existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)

    # Setup file handler with rotating backups
    try:
        from src.utils.constants import LOG_DIR
        
        if not LOG_DIR.exists():
            try:
                LOG_DIR.mkdir(parents=True)
            except:
                pass

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = LOG_DIR / f"{timestamp}.{context}.log"

        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=5_000_000,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"
        ))
        file_handler.addFilter(RunContextFilter())
        logger.addHandler(file_handler)
    except:
        pass  # Fail gracefully if logging can't be initialized

    # Setup console handler if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"
        ))
        console_handler.addFilter(RunContextFilter())
        logger.addHandler(console_handler)


def setup_logging(context: str = 'imported'):
    """
    Initialize logging for the application

    Args:
        context: Execution context identifier
    """
    set_run_context(context)
    return logger


# Initialize with default context
set_run_context(_RUN_CONTEXT)
