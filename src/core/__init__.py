"""
================================================================================
CORE MODULE - Core Business Logic
================================================================================

Central package for Transaction calculation engine and data management.

Exported Classes:
    DatabaseManager - SQLite transaction database operations
    DatabaseEncryption - Two-layer encryption for database protection
    TransactionEngine - Main Transaction calculation engine (via engine.py)
    TransactionReviewer - Audit risk detection (via reviewer.py)

Exported Functions:
    Encryption helpers:
        - encrypt_api_keys, decrypt_api_keys
        - encrypt_wallets, decrypt_wallets
        - load_api_keys_file, save_api_keys_file
        - load_wallets_file, save_wallets_file
        - get_api_key_cipher, get_wallet_cipher

Usage:
    from src.core import DatabaseManager, TransactionEngine
    from src.core.encryption import encrypt_api_keys

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

from src.core.database import DatabaseManager
from src.core.encryption import (
    DatabaseEncryption,
    encrypt_api_keys,
    decrypt_api_keys,
    encrypt_wallets,
    decrypt_wallets,
    load_api_keys_file,
    save_api_keys_file,
    load_wallets_file,
    save_wallets_file,
    get_api_key_cipher,
    get_wallet_cipher
)

__all__ = [
    'DatabaseManager',
    'DatabaseEncryption',
    'encrypt_api_keys',
    'decrypt_api_keys',
    'encrypt_wallets',
    'decrypt_wallets',
    'load_api_keys_file',
    'save_api_keys_file',
    'load_wallets_file',
    'save_wallets_file',
    'get_api_key_cipher',
    'get_wallet_cipher',
]
