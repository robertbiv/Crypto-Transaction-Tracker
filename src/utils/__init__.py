"""
================================================================================
UTILS MODULE - Shared Utilities and Helpers
================================================================================

Shared infrastructure used across all application components.

Exported Functions:
    Logging:
        - setup_logging() - Initialize logging infrastructure
        - set_run_context(context) - Set execution context
        - logger - Main application logger
    
    Configuration:
        - load_config() - Load configuration from config.json
        - get_status() - Read application status
        - update_status() - Update application status
        - mark_data_changed() - Flag data modifications
        - mark_run_complete() - Record successful run
    
    Constants:
        - All system constants via wildcard import
        - File paths, tax rules, API limits, etc.

Usage:
    from src.utils import logger, load_config
    from src.utils.constants import WASH_SALE_WINDOW_DAYS

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

from .logger import setup_logging, set_run_context, logger
from .constants import *
from .config import load_config, get_status, update_status, mark_data_changed, mark_run_complete

__all__ = [
    'setup_logging',
    'set_run_context',
    'logger',
    'load_config',
    'get_status',
    'update_status',
    'mark_data_changed',
    'mark_run_complete',
]
