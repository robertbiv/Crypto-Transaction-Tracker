"""
================================================================================
CONSTANTS - System-Wide Configuration Values
================================================================================

Centralized repository for all hardcoded constants used throughout the
Transaction calculation engine. Organized by functional category.

Constant Categories:
    1. File Paths - Directory and file locations
    2. Transaction Calculation - IRS rules and precision settings
    3. Database - SQLite configuration and safety limits
    4. API - External service rate limits and timeouts
    5. Compliance - Regulatory constants
    6. DeFi Patterns - Protocol identification strings

Key Constants:
    
    Transaction Calculation:
        WASH_SALE_WINDOW_DAYS = 30
            IRS wash sale rule: 30 days before AND after (61-day total)
        
        LONG_TERM_HOLDING_DAYS = 365
            Minimum days for long-term capital gains treatment
        
        DECIMAL_PRECISION = 8
            Cryptocurrency decimal places (satoshi/wei level)
        
        USD_PRECISION = 2
            US Dollar rounding precision
    
    Database:
        DB_ENCRYPTION_ITERATIONS = 480000
            PBKDF2 iterations (OWASP 2023 recommendation)
        
        DB_RETRY_ATTEMPTS = 3
            Retries for failed database operations
    
    API:
        API_TIMEOUT_SECONDS = 10
            HTTP request timeout
        
        API_RETRY_MAX_ATTEMPTS = 3
            Maximum retries for failed API calls

File Path Constants:
    All paths are relative to BASE_DIR (project root)
    Supports monkeypatching for test isolation
    
    Example:
        DB_FILE = BASE_DIR / 'crypto_master.db'
        INPUT_DIR = BASE_DIR / 'inputs'
        OUTPUT_DIR = BASE_DIR / 'outputs'

DeFi Protocol Patterns:
    Used to identify liquidity pool tokens and wrapped assets:
        ['UNI-V2', 'UNI-V3', 'SUSHI', 'CURVE', 'BALANCER', 
         'AAVE', 'COMPOUND', '-LP', '_LP', 'POOL']

Usage:
    from src.utils.constants import WASH_SALE_WINDOW_DAYS, DB_FILE
    
    window_start = sale_date - timedelta(days=WASH_SALE_WINDOW_DAYS)
    conn = sqlite3.connect(str(DB_FILE))

Note:
    Values in this file are STATIC. For runtime-configurable settings,
    use config.json via src.utils.config module.

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import os
from pathlib import Path
from decimal import Decimal

# ==========================================
# FILE PATHS
# ==========================================
BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / 'inputs'
ARCHIVE_DIR = BASE_DIR / 'processed_archive'
OUTPUT_DIR = BASE_DIR / 'outputs'
LOG_DIR = OUTPUT_DIR / 'logs'
DB_FILE = BASE_DIR / 'crypto_master.db'
DB_BACKUP = BASE_DIR / 'crypto_master.db.bak'
DB_KEY_FILE = BASE_DIR / 'keys' / '.db_key'
DB_SALT_FILE = BASE_DIR / 'keys' / '.db_salt'
KEYS_FILE = BASE_DIR / 'api_keys.json'
API_KEYS_ENCRYPTED_FILE = BASE_DIR / 'keys' / 'api_keys_encrypted.json'
WALLETS_FILE = BASE_DIR / 'wallets.json'
WALLETS_ENCRYPTED_FILE = BASE_DIR / 'keys' / 'wallets_encrypted.json'
API_KEY_ENCRYPTION_FILE = BASE_DIR / 'keys' / 'api_key_encryption.key'
WEB_ENCRYPTION_KEY_FILE = BASE_DIR / 'keys' / 'web_encryption.key'
CONFIG_FILE = BASE_DIR / 'configs' / 'config.json'
STATUS_FILE = BASE_DIR / 'configs' / 'status.json'
CACHED_TOKEN_FILE = BASE_DIR / 'configs' / 'stablecoins_cache.json'

# ==========================================
# Transaction CALCULATION CONSTANTS
# ==========================================
"""
IRS and regulatory compliance constants for US Transaction calculations
"""
WASH_SALE_WINDOW_DAYS = 30  # Days before and after (total 61-day window)
DECIMAL_PRECISION = 8  # Cryptocurrency precision (satoshi/wei level)
USD_PRECISION = 2  # US Dollar rounding precision
LONG_TERM_HOLDING_DAYS = 365  # Days threshold for long-term capital gains treatment

# ==========================================
# DATABASE CONSTANTS
# ==========================================
"""
Database configuration and safety parameters
"""
MAX_DB_BACKUP_SIZE_MB = 100  # Maximum database backup size in MB
DB_RETRY_ATTEMPTS = 3  # Number of retry attempts for failed database operations
DB_RETRY_DELAY_MS = 100  # Milliseconds to wait between retry attempts
DB_ENCRYPTION_SALT_LENGTH = 16  # Salt length in bytes for key derivation
DB_ENCRYPTION_ITERATIONS = 480000  # PBKDF2 iterations (OWASP 2023 recommendation)

# ==========================================
# API CONSTANTS
# ==========================================
"""
External API rate limiting and timeout settings
"""
API_RETRY_MAX_ATTEMPTS = 3  # Maximum number of retries for failed API calls
API_RETRY_DELAY_MS = 1000  # Initial delay between retries in milliseconds
API_TIMEOUT_SECONDS = 10  # Timeout for API requests in seconds

# ==========================================
# DEFI PROTOCOL PATTERNS
# ==========================================
"""
Patterns used to identify DeFi LP tokens and related protocol assets
"""
DEFI_LP_PATTERNS = [
    'UNI-V2', 'UNI-V3', 'SUSHI', 'CURVE', 'BALANCER', 'AAVE',
    'COMPOUND', 'MAKER', 'YEARN', '-LP', '_LP', 'POOL'
]

# ==========================================
# COMPLIANCE CONFIGURATION
# ==========================================
"""
Default compliance settings - can be overridden in config.json
"""
STRICT_BROKER_MODE = True  # Enforce broker reporting alignment
STAKING_transactionABLE_ON_RECEIPT = True  # IRS constructive receipt position
DEFI_LP_CONSERVATIVE = True  # Conservative DeFi treatment
COLLECTIBLE_PREFIXES = {'NFT-', 'ART-'}  # Prefixes for 28% collectible gains
COLLECTIBLE_TOKENS = {'NFT', 'PUNK', 'BAYC'}  # Token names treated as collectibles

# Default exchange classifications
DOMESTIC_EXCHANGES = {
    'COINBASE', 'KRAKEN', 'GEMINI', 'BITSTAMP', 'ITBIT',
    'BINANCE.US', 'CASH APP', 'SQUARE', 'STRIKE', 'RIVER',
    'SWAN BITCOIN', 'LEDGER LIVE', 'TREZOR', 'COLD STORAGE'
}

FOREIGN_EXCHANGES = {
    'BINANCE', 'BINANCE.COM', 'BYBIT', 'OKX', 'KUCOIN',
    'GATE.IO', 'HUOBI', 'CRYPTO.COM', 'FTX.COM', 'FTX', 'UPBIT', 'BITHUMB',
    'COINCHECK', 'LIQUID', 'DERIBIT', 'KRAKEN EU', 'BITSTAMP EU',
    'REVOLUT', 'LMAX', 'THEROCK', 'MEXC', 'ASCENDEX', 'HOTBIT',
    'BITFINEX', 'POLONIEX'
}

# ==========================================
# COMPLIANCE WARNINGS
# ==========================================
"""
Warnings displayed when non-standard compliance settings are detected
"""
COMPLIANCE_WARNINGS = {
    'HIFO': '[CONFIG] Accounting method HIFO selected. Not IRS-recommended and may cause 1099-DA mismatches.',
    'STRICT_BROKER_DISABLED': '[CONFIG] strict_broker_mode disabled. Cross-wallet basis fallback may cause reporting issues.',
    'CONSTRUCTIVE_RECEIPT': '[CONFIG] staking_transactionable_on_receipt=False. Deferral stance is aggressive.',
    'DEFI_LP_AGGRESSIVE': '[CONFIG] defi_lp_conservative=False. LP deposits treated as non-Reportable. AGGRESSIVE.',
}

# ==========================================
# RUNTIME CONTEXT
# ==========================================
"""
Global state for run context (auto-runner, web UI, CLI, etc)
"""
CURRENT_YEAR_OVERRIDE = None
RUN_CONTEXT = 'imported'  # Can be: 'imported', 'autorunner', 'web', 'cli', 'test'


# ==========================================
# SECURITY CONSTANTS
# ==========================================
"""
Web UI security configuration
"""
LOGIN_RATE_LIMIT = "5 per 15 minutes"
API_RATE_LIMIT = "100 per hour"
CSRF_TOKEN_ROTATION_INTERVAL = 3600  # seconds
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
BCRYPT_COST_FACTOR = 12

# API Rate Limiting for Interactive Fixer
TEST_MODE = os.environ.get('TEST_MODE') == '1'
API_REQUEST_DELAY = 0.3  # Seconds between API requests
API_BATCH_DELAY = 2  # Seconds after processing batch
API_MAX_RETRIES = 5  # Maximum retry attempts
API_INITIAL_BACKOFF = 1  # Initial backoff delay
API_MAX_RETRY_WAIT = 1 if TEST_MODE else 60  # Max wait for rate limits
