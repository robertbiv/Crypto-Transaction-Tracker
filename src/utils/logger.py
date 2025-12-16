"""
Logger Configuration Module

Provides unified logging across the application with support for:
- Multiple run contexts (CLI, web, auto-runner, tests)
- File and console output
- Context-aware filtering
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
