"""
Configuration Management Module

Handles loading, validating, and updating application configuration from config.json
Supports hot-reload and merging with defaults
"""

import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("crypto_tax_engine")


def load_config():
    """
    Load configuration from config.json with sensible defaults

    Returns:
        dict: Configuration dictionary
    """
    from .constants import CONFIG_FILE
    
    defaults = {
        "general": {
            "run_audit": True,
            "create_db_backups": True,
        },
        "accounting": {
            "method": "FIFO",  # FIFO, HIFO, etc.
            "include_fees_in_basis": True,
        },
        "compliance": {
            "strict_broker_mode": True,
            "broker_sources": [
                "COINBASE", "KRAKEN", "GEMINI", "BINANCE",
                "ROBINHOOD", "ETORO"
            ],
            "staking_taxable_on_receipt": True,
            "defi_lp_conservative": True,
            "collectible_prefixes": ["NFT-", "ART-"],
            "collectible_tokens": ["NFT", "PUNK", "BAYC"],
        },
        "api": {
            "retry_attempts": 3,
            "timeout_seconds": 10,
        },
    }

    if not CONFIG_FILE.exists():
        _save_config(CONFIG_FILE, defaults)
        return defaults

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        # Merge with defaults to ensure all keys exist
        merged = _deep_merge(defaults, config)

        # Save merged config back if anything was added
        if merged != config:
            _save_config(CONFIG_FILE, merged)

        return merged
    except json.JSONDecodeError as e:
        logger.error(f"Config file corrupted: {e}. Using defaults.")
        return defaults
    except Exception as e:
        logger.error(f"Error loading config: {e}. Using defaults.")
        return defaults


def _deep_merge(defaults: dict, override: dict) -> dict:
    """
    Deep merge override config into defaults, preserving new defaults

    Args:
        defaults: Default configuration
        override: User-provided configuration

    Returns:
        dict: Merged configuration
    """
    result = defaults.copy()
    for key, value in override.items():
        if key in defaults and isinstance(defaults[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(defaults[key], value)
        else:
            result[key] = value
    return result


def _save_config(config_file: Path, config: dict):
    """
    Save configuration to file

    Args:
        config_file: Path to config file
        config: Configuration dictionary
    """
    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def get_status():
    """
    Get system status including timestamps

    Returns:
        dict: Status dictionary with last_data_change, last_run, etc.
    """
    from .constants import STATUS_FILE
    
    default_status = {
        'last_data_change': None,
        'last_run': None,
        'last_run_success': False
    }

    if not STATUS_FILE.exists():
        return default_status

    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except:
        return default_status


def update_status(key: str, value):
    """
    Update a specific status key

    Args:
        key: Status key to update
        value: New value
    """
    from .constants import STATUS_FILE
    
    status = get_status()
    status[key] = value

    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to update status: {e}")


def mark_data_changed():
    """Mark that data has changed (requires re-run)"""
    update_status('last_data_change', datetime.now().isoformat())


def mark_run_complete(success: bool = True):
    """Mark that calculation run completed"""
    update_status('last_run', datetime.now().isoformat())
    update_status('last_run_success', success)
