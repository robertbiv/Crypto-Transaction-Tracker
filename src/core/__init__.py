"""
Core Business Logic Module

Contains core functionality for database and encryption operations:
- DatabaseManager: SQLite transaction management
- DatabaseEncryption: Two-layer encryption for database protection
- Encryption helpers: API keys and wallet encryption
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
