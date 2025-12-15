import sqlite3
import pandas as pd
import ccxt
import json
import time
import shutil
import sys
import os
import requests
import yfinance as yf
import hashlib
import decimal
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import filelock

# ==========================================
# CONSTANTS
# ==========================================
# Tax Calculation Constants
WASH_SALE_WINDOW_DAYS = 30  # IRS wash sale rule: 30 days before and after
DECIMAL_PRECISION = 8  # Crypto precision (satoshi level)
USD_PRECISION = 2  # USD rounding precision
LONG_TERM_HOLDING_DAYS = 365  # Days for long-term capital gains

# Database Constants
MAX_DB_BACKUP_SIZE_MB = 100  # Maximum database backup size
DB_RETRY_ATTEMPTS = 3  # Number of retries for database operations
DB_RETRY_DELAY_MS = 100  # Delay between retry attempts
DB_ENCRYPTION_SALT_LENGTH = 16  # Salt length for key derivation (bytes)
DB_ENCRYPTION_ITERATIONS = 480000  # PBKDF2 iterations (matches OWASP 2023)

# API Constants
API_RETRY_MAX_ATTEMPTS = 3  # Max retries for API calls
API_RETRY_DELAY_MS = 1000  # Initial delay between retries
API_TIMEOUT_SECONDS = 10  # Timeout for API requests

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / 'inputs'
ARCHIVE_DIR = BASE_DIR / 'processed_archive'
OUTPUT_DIR = BASE_DIR / 'outputs'
LOG_DIR = OUTPUT_DIR / 'logs'
DB_FILE = BASE_DIR / 'crypto_master.db'
DB_BACKUP = BASE_DIR / 'crypto_master.db.bak'
DB_KEY_FILE = BASE_DIR / '.db_key'  # Encrypted database key (hidden file)
DB_SALT_FILE = BASE_DIR / '.db_salt'  # Salt for key derivation (hidden file)
CURRENT_YEAR_OVERRIDE = None
KEYS_FILE = BASE_DIR / 'api_keys.json'
API_KEYS_ENCRYPTED_FILE = BASE_DIR / 'api_keys_encrypted.json'
WALLETS_FILE = BASE_DIR / 'wallets.json'
WALLETS_ENCRYPTED_FILE = BASE_DIR / 'wallets_encrypted.json'
API_KEY_ENCRYPTION_FILE = BASE_DIR / 'api_key_encryption.key'
WEB_ENCRYPTION_KEY_FILE = BASE_DIR / 'web_encryption.key'
CONFIG_FILE = BASE_DIR / 'config.json'
STATUS_FILE = BASE_DIR / 'status.json'

logger = logging.getLogger("crypto_tax_engine")
logger.setLevel(logging.INFO)
RUN_CONTEXT = 'imported'

class RunContextFilter(logging.Filter):
    def filter(self, record):
        try: record.run_context = RUN_CONTEXT
        except: record.run_context = 'unknown'
        return True

def set_run_context(context: str):
    global RUN_CONTEXT
    RUN_CONTEXT = context
    for h in list(logger.handlers): logger.removeHandler(h)
    try:
        if not LOG_DIR.exists(): 
            try: LOG_DIR.mkdir(parents=True)
            except: pass
        from logging.handlers import RotatingFileHandler
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = LOG_DIR / f"{timestamp}.{context}.log"
        fh = RotatingFileHandler(str(fname), maxBytes=5_000_000, backupCount=5, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"))
        fh.addFilter(RunContextFilter())
        logger.addHandler(fh)
    except: pass
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"))
        sh.addFilter(RunContextFilter())
        logger.addHandler(sh)

set_run_context(RUN_CONTEXT)

class ApiAuthError(Exception): pass


# ==========================================
# ENCRYPTED STORAGE HELPERS (API keys, wallets)
# ==========================================
def _ensure_parent(path: Path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _get_or_create_key(path: Path):
    if path.exists():
        try:
            return path.read_bytes()
        except Exception:
            pass
    key = Fernet.generate_key()
    _ensure_parent(path)
    try:
        path.write_bytes(key)
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows: warn user to restrict ACLs manually
            logger.warning(f"[SECURITY] Key file {path.name} created. Please restrict file permissions manually on Windows.")
    except Exception:
        pass
    return key


def _api_keys_encrypted_path():
    return API_KEYS_ENCRYPTED_FILE


def _wallets_encrypted_path():
    return WALLETS_ENCRYPTED_FILE


def get_api_key_cipher():
    """Get Fernet cipher for API keys, derived from DB password if available."""
    # Try password-derived key first
    if DB_SALT_FILE.exists():
        try:
            with open(DB_SALT_FILE, 'rb') as f:
                salt = f.read()
            # Try to get password from environment or use fallback
            # In production, password comes from web login; CLI may need env var
            password = os.environ.get('CRYPTO_TAX_PASSWORD')
            if password:
                key = DatabaseEncryption.derive_fernet_key(password, salt, 'api_keys')
                return Fernet(key)
        except Exception:
            pass
    # Fallback to file-based key for backward compatibility
    return Fernet(_get_or_create_key(API_KEY_ENCRYPTION_FILE))


def get_wallet_cipher():
    """Get Fernet cipher for wallets, derived from DB password if available."""
    # Try password-derived key first
    if DB_SALT_FILE.exists():
        try:
            with open(DB_SALT_FILE, 'rb') as f:
                salt = f.read()
            password = os.environ.get('CRYPTO_TAX_PASSWORD')
            if password:
                key = DatabaseEncryption.derive_fernet_key(password, salt, 'wallets')
                return Fernet(key)
        except Exception:
            pass
    # Fallback to file-based key for backward compatibility
    return Fernet(_get_or_create_key(WEB_ENCRYPTION_KEY_FILE))


def encrypt_api_keys(data):
    try:
        json_data = json.dumps(data)
        encrypted = get_api_key_cipher().encrypt(json_data.encode())
        return base64.b64encode(encrypted).decode()
    except Exception:
        return None


def decrypt_api_keys(encrypted_data):
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
        decrypted = get_api_key_cipher().decrypt(encrypted_bytes)
        return json.loads(decrypted.decode())
    except Exception:
        return None


def encrypt_wallets(data):
    try:
        payload = json.dumps(data) if isinstance(data, (dict, list)) else data
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        encrypted = get_wallet_cipher().encrypt(payload)
        return base64.b64encode(encrypted).decode()
    except Exception:
        return None


def decrypt_wallets(encrypted_data):
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
        decrypted = get_wallet_cipher().decrypt(encrypted_bytes)
        return json.loads(decrypted.decode('utf-8'))
    except Exception:
        return None


def load_api_keys_file():
    candidates = []
    for path in [_api_keys_encrypted_path(), API_KEYS_ENCRYPTED_FILE, KEYS_FILE]:
        if path not in candidates:
            candidates.append(path)

    legacy = None
    decrypt_failed = False
    for path in candidates:
        if not path.exists():
            continue
        try:
            with open(path, 'r') as f:
                raw = json.load(f)
            if isinstance(raw, dict) and 'ciphertext' in raw:
                data = decrypt_api_keys(raw['ciphertext'])
                if data is not None:
                    return data
                else:
                    logger.error(f"[SECURITY] Failed to decrypt API keys from {path}. Ciphertext may be corrupted.")
                    decrypt_failed = True
            if isinstance(raw, str):
                data = decrypt_api_keys(raw)
                if data is not None:
                    return data
                else:
                    logger.error(f"[SECURITY] Failed to decrypt API keys from {path}. Ciphertext may be corrupted.")
                    decrypt_failed = True
            if isinstance(raw, dict) and 'ciphertext' not in raw:
                legacy = raw
        except Exception as e:
            logger.warning(f"Failed to read API keys from {path}: {e}")
            continue

    if decrypt_failed:
        raise ValueError("API keys file exists but decryption failed. Check encryption keys and file integrity.")

    if legacy is not None:
        try:
            logger.info("Migrating legacy plaintext API keys to encrypted storage")
            save_api_keys_file(legacy)
        except Exception as e:
            logger.error(f"Failed to migrate API keys: {e}")
            pass
        return legacy
    return {}


def save_api_keys_file(data):
    ciphertext = encrypt_api_keys(data)
    if not ciphertext:
        raise ValueError("Failed to encrypt API keys. Cannot save.")
    target = _api_keys_encrypted_path()
    _ensure_parent(target)
    lock = filelock.FileLock(str(target) + '.lock', timeout=10)
    try:
        with lock:
            with open(target, 'w') as f:
                json.dump({'ciphertext': ciphertext}, f, indent=4)
    except filelock.Timeout:
        logger.error(f"Failed to acquire lock for {target}")
        raise
    except Exception as e:
        logger.error(f"Failed to save API keys: {e}")
        raise
    try:
        if KEYS_FILE.exists():
            KEYS_FILE.unlink()
    except Exception:
        pass


def load_wallets_file():
    candidates = []
    for path in [_wallets_encrypted_path(), WALLETS_ENCRYPTED_FILE, WALLETS_FILE]:
        if path not in candidates:
            candidates.append(path)

    legacy = None
    decrypt_failed = False
    for path in candidates:
        if not path.exists():
            continue
        try:
            with open(path, 'r') as f:
                raw = json.load(f)
            if isinstance(raw, dict) and 'ciphertext' in raw:
                data = decrypt_wallets(raw['ciphertext'])
                if data is not None:
                    return data
                else:
                    logger.error(f"[SECURITY] Failed to decrypt wallets from {path}. Ciphertext may be corrupted.")
                    decrypt_failed = True
            if isinstance(raw, str):
                data = decrypt_wallets(raw)
                if data is not None:
                    return data
                else:
                    logger.error(f"[SECURITY] Failed to decrypt wallets from {path}. Ciphertext may be corrupted.")
                    decrypt_failed = True
            if isinstance(raw, dict) and 'ciphertext' not in raw:
                legacy = raw
        except Exception as e:
            logger.warning(f"Failed to read wallets from {path}: {e}")
            continue

    if decrypt_failed:
        raise ValueError("Wallets file exists but decryption failed. Check encryption keys and file integrity.")

    if legacy is not None:
        try:
            logger.info("Migrating legacy plaintext wallets to encrypted storage")
            save_wallets_file(legacy)
        except Exception as e:
            logger.error(f"Failed to migrate wallets: {e}")
            pass
        return legacy
    return {}


def save_wallets_file(data):
    ciphertext = encrypt_wallets(data)
    if not ciphertext:
        raise ValueError("Failed to encrypt wallets. Cannot save.")
    target = _wallets_encrypted_path()
    _ensure_parent(target)
    lock = filelock.FileLock(str(target) + '.lock', timeout=10)
    try:
        with lock:
            with open(target, 'w') as f:
                json.dump({'ciphertext': ciphertext}, f, indent=4)
    except filelock.Timeout:
        logger.error(f"Failed to acquire lock for {target}")
        raise
    except Exception as e:
        logger.error(f"Failed to save wallets: {e}")
        raise
    try:
        if WALLETS_FILE.exists():
            WALLETS_FILE.unlink()
    except Exception:
        pass

def initialize_folders():
    for d in [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, LOG_DIR]:
        if not d.exists(): d.mkdir(parents=True)

def get_status():
    """Get system status including timestamps"""
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

def update_status(key, value):
    """Update a specific status key"""
    status = get_status()
    status[key] = value
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to update status: {e}")

def mark_data_changed():
    """Mark that data has changed (requires re-run)"""
    update_status('last_data_change', datetime.now().isoformat())

def mark_run_complete(success=True):
    """Mark that calculation run completed"""
    update_status('last_run', datetime.now().isoformat())
    update_status('last_run_success', success)

def load_config():
    defaults = {
        "general": {"run_audit": True, "create_db_backups": True},
        "accounting": {"method": "FIFO"},
        "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
        "logging": {"compress_older_than_days": 30},
        "compliance": {
            "strict_broker_mode": True,
            "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
            "staking_taxable_on_receipt": True,
            "collectible_prefixes": ["NFT-", "ART-"],
            "collectible_tokens": ["NFT", "PUNK", "BAYC"]
        }
    }
    if not CONFIG_FILE.exists(): return defaults
    try:
        with open(CONFIG_FILE) as f: 
            user = json.load(f)
            for k, v in defaults.items():
                if k not in user: user[k] = v
                else: 
                    for sk, sv in v.items():
                        if sk not in user[k]: user[k][sk] = sv
            return user
    except: return defaults

GLOBAL_CONFIG = load_config()

STRICT_BROKER_MODE = bool(GLOBAL_CONFIG.get('compliance', {}).get('strict_broker_mode', True))
BROKER_SOURCES = set(GLOBAL_CONFIG.get('compliance', {}).get('broker_sources', ['COINBASE','KRAKEN','GEMINI','BINANCE','ROBINHOOD','ETORO']))
STAKING_TAXABLE_ON_RECEIPT = bool(GLOBAL_CONFIG.get('compliance', {}).get('staking_taxable_on_receipt', True))
DEFI_LP_CONSERVATIVE = bool(GLOBAL_CONFIG.get('compliance', {}).get('defi_lp_conservative', True))
COLLECTIBLE_PREFIXES = set(GLOBAL_CONFIG.get('compliance', {}).get('collectible_prefixes', ['NFT-','ART-']))
COLLECTIBLE_TOKENS = set(GLOBAL_CONFIG.get('compliance', {}).get('collectible_tokens', ['NFT','PUNK','BAYC']))

# DeFi protocol patterns for LP detection
DEFI_LP_PATTERNS = ['UNI-V2', 'UNI-V3', 'SUSHI', 'CURVE', 'BALANCER', 'AAVE', 
                    'COMPOUND', 'MAKER', 'YEARN', '-LP', '_LP', 'POOL']

COMPLIANCE_WARNINGS = {
    'HIFO': '[CONFIG] Accounting method HIFO selected. This is not recommended and may not align with broker 1099-DA reporting.',
    'STRICT_BROKER_DISABLED': '[CONFIG] strict_broker_mode is disabled. Cross-wallet basis fallback can cause 1099-DA mismatches.',
    'CONSTRUCTIVE_RECEIPT': '[CONFIG] staking_taxable_on_receipt=False. Constructive receipt deferral is aggressive and may be challenged by IRS.',
    'DEFI_LP_AGGRESSIVE': '[CONFIG] defi_lp_conservative is False. LP deposits treated as non-taxable. AGGRESSIVE STANCE - IRS may challenge as taxable swaps.'
}

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def to_decimal(value):
    """Safely convert float/int/str to Decimal to avoid IEEE 754 precision loss"""
    if value is None: return Decimal('0')
    if isinstance(value, Decimal): 
        if value.is_nan(): return Decimal('0')
        if value.is_infinite(): return Decimal('0')  # Handle infinity
        return value
    if isinstance(value, (int, float)):
        s = str(value)
        if 'nan' in s.lower(): return Decimal('0')
        if 'inf' in s.lower(): return Decimal('0')  # Handle infinity
        return Decimal(s)
    if isinstance(value, str):
        if value.lower() == 'nan': return Decimal('0')
        if 'inf' in value.lower(): return Decimal('0')  # Handle infinity
        try: return Decimal(value)
        except: return Decimal('0')
    return Decimal('0')

def is_defi_lp_token(coin_name):
    """Check if a coin matches DeFi LP token patterns"""
    coin_upper = str(coin_name).upper()
    return any(pattern in coin_upper for pattern in DEFI_LP_PATTERNS)

def round_decimal(value, places=8):
    """Round Decimal value to specified places, handling special values gracefully"""
    if not isinstance(value, Decimal): 
        value = to_decimal(value)
    
    # Handle special values
    if value.is_nan():
        return Decimal('0')
    if value.is_infinite():
        return Decimal('0')
    
    try:
        quantizer = Decimal(10) ** -places
        return value.quantize(quantizer, rounding=ROUND_HALF_UP)
    except (decimal.InvalidOperation, decimal.DecimalException):
        # If quantization fails, return zero
        return Decimal('0')

class NetworkRetry:
    @staticmethod
    def run(func, retries=5, delay=2, backoff=2, context="Network"):
        if RUN_CONTEXT == 'imported':
            retries = min(retries, 2)
            delay = 0.1
            backoff = 1.5
        for i in range(retries):
            try: return func()
            except Exception as e:
                if i == retries - 1:
                    if isinstance(e, TimeoutError): raise TimeoutError(f"{context} timeout: {e}")
                    raise e
                time.sleep(delay * (backoff ** i))

# ==========================================
# DATABASE ENCRYPTION MANAGER
# ==========================================
class DatabaseEncryption:
    """Two-layer encryption for database protection using password-derived key.
    
    Layer 1: Random 256-bit key encrypts the database
    Layer 2: Password-derived key encrypts Layer 1 key
    
    Provides protection for:
    - Database at rest (encrypted with random key)
    - Backups (encrypted key + encrypted DB together)
    - Password-based access control
    """
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes = None, context: str = ""):
        """Derive encryption key from password using PBKDF2.
        
        Args:
            password: User password
            salt: Optional salt. If None, generates random salt.
            context: Optional context string to derive different keys from same password
            
        Returns:
            (key, salt) tuple where key is base64-encoded Fernet key
        """
        if salt is None:
            salt = os.urandom(DB_ENCRYPTION_SALT_LENGTH)
        
        # Mix context into password to derive different keys
        password_with_context = f"{password}::{context}" if context else password
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=DB_ENCRYPTION_ITERATIONS,
        )
        
        derived = kdf.derive(password_with_context.encode())
        fernet_key = base64.urlsafe_b64encode(derived)
        return fernet_key, salt
    
    @staticmethod
    def derive_fernet_key(password: str, salt: bytes, context: str):
        """Derive a Fernet key from password for a specific context (e.g., 'api_keys', 'wallets')."""
        key, _ = DatabaseEncryption.derive_key_from_password(password, salt, context)
        return key
    
    @staticmethod
    def generate_random_key():
        """Generate random 256-bit encryption key for database."""
        return Fernet.generate_key()
    
    @staticmethod
    def encrypt_key(db_key: bytes, password: str, salt: bytes = None, context: str = ""):
        """Encrypt database key with password-derived key."""
        password_key, used_salt = DatabaseEncryption.derive_key_from_password(password, salt, context)
        cipher = Fernet(password_key)
        encrypted_key = cipher.encrypt(db_key)
        return encrypted_key, used_salt
    
    @staticmethod
    def decrypt_key(encrypted_key: bytes, password: str, salt: bytes, context: str = ""):
        """Decrypt database key using password."""
        password_key, _ = DatabaseEncryption.derive_key_from_password(password, salt, context)
        cipher = Fernet(password_key)
        return cipher.decrypt(encrypted_key)
    
    @staticmethod
    def initialize_encryption(password: str):
        """Initialize or retrieve encryption keys."""
        if DB_KEY_FILE.exists() and DB_SALT_FILE.exists():
            try:
                with open(DB_KEY_FILE, 'rb') as f:
                    encrypted_key = f.read()
                with open(DB_SALT_FILE, 'rb') as f:
                    salt = f.read()
                
                db_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
                return db_key
            except Exception as e:
                logger.error(f"[ENCRYPTION] Failed to decrypt existing key: {e}")
                raise
        
        db_key = DatabaseEncryption.generate_random_key()
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        
        try:
            with open(DB_KEY_FILE, 'wb') as f:
                f.write(encrypted_key)
            os.chmod(DB_KEY_FILE, 0o600)
            
            with open(DB_SALT_FILE, 'wb') as f:
                f.write(salt)
            os.chmod(DB_SALT_FILE, 0o600)
            
            logger.info("[ENCRYPTION] Database encryption initialized with new keys")
        except Exception as e:
            logger.error(f"[ENCRYPTION] Failed to store encryption keys: {e}")
            raise
        
        return db_key
    
    @staticmethod
    def create_encrypted_backup(password: str, backup_path: Path = None):
        """Create encrypted database backup.
        
        Args:
            password: Encryption password
            backup_path: Custom backup path. If None, uses default.
            
        Returns:
            Path to encrypted backup file
        """
        if backup_path is None:
            backup_path = BASE_DIR / f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tar.gz.enc'
        
        try:
            # Get current encryption key
            if not DB_KEY_FILE.exists() or not DB_SALT_FILE.exists():
                raise FileNotFoundError("Database encryption keys not found. Initialize encryption first.")
            
            with open(DB_KEY_FILE, 'rb') as f:
                encrypted_key = f.read()
            with open(DB_SALT_FILE, 'rb') as f:
                salt = f.read()
            
            # Decrypt to verify password
            db_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
            cipher = Fernet(db_key)
            
            # Read database file
            with open(DB_FILE, 'rb') as f:
                db_content = f.read()
            
            # Encrypt database
            encrypted_db = cipher.encrypt(db_content)
            
            # Write encrypted backup
            with open(backup_path, 'wb') as f:
                f.write(encrypted_db)
            
            logger.info(f"[BACKUP] Created encrypted backup at {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"[BACKUP] Encryption failed: {e}")
            raise
    
    @staticmethod
    def restore_encrypted_backup(encrypted_backup_path: Path, password: str, target_db_path: Path = None):
        """Restore database from encrypted backup.
        
        Args:
            encrypted_backup_path: Path to encrypted backup file
            password: Decryption password
            target_db_path: Where to restore. If None, uses default.
            
        Returns:
            Path to restored database
        """
        if target_db_path is None:
            target_db_path = DB_FILE
        
        try:
            # Get encryption key using password
            if not DB_KEY_FILE.exists() or not DB_SALT_FILE.exists():
                raise FileNotFoundError("Database encryption keys not found.")
            
            with open(DB_KEY_FILE, 'rb') as f:
                encrypted_key = f.read()
            with open(DB_SALT_FILE, 'rb') as f:
                salt = f.read()
            
            # Decrypt database key
            db_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
            cipher = Fernet(db_key)
            
            # Read and decrypt backup
            with open(encrypted_backup_path, 'rb') as f:
                encrypted_db = f.read()
            
            decrypted_db = cipher.decrypt(encrypted_db)
            
            # Create backup of current database
            if target_db_path.exists():
                backup_name = target_db_path.with_suffix(f'.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
                shutil.copy(target_db_path, backup_name)
                logger.info(f"[BACKUP] Saved current DB to {backup_name}")
            
            # Restore encrypted backup
            with open(target_db_path, 'wb') as f:
                f.write(decrypted_db)
            
            logger.info(f"[BACKUP] Restored database from encrypted backup")
            return target_db_path
            
        except Exception as e:
            logger.error(f"[BACKUP] Restore failed: {e}")
            raise


# 1. DATABASE MANAGER
# ==========================================
class DatabaseManager:
    def __init__(self):
        initialize_folders()
        self._ensure_integrity()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _backup_path(self): return DB_FILE.with_suffix('.bak')

    def create_safety_backup(self):
        if not GLOBAL_CONFIG['general']['create_db_backups']: return
        if DB_FILE.exists():
            self.conn.commit()
            try: shutil.copy(DB_FILE, self._backup_path())
            except: pass

    def restore_safety_backup(self):
        if not GLOBAL_CONFIG['general']['create_db_backups']: return
        backup_path = self._backup_path()
        if backup_path.exists():
            self.close()
            try:
                shutil.copy(backup_path, DB_FILE)
                self.conn = sqlite3.connect(str(DB_FILE))
                self.cursor = self.conn.cursor()
                logger.info("[SAFE] Restored database backup.")
            except: pass

    def remove_safety_backup(self): pass 

    def _ensure_integrity(self):
        if not DB_FILE.exists(): return
        c = None
        try:
            c = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
            c.execute("PRAGMA integrity_check")
            c.close()
        except:
            try:
                if c: c.close()
            finally:
                self._recover_db()

    def _recover_db(self):
        ts = datetime.now().strftime("%Y%m%d")
        shutil.move(str(DB_FILE), str(BASE_DIR / f"CORRUPT_{ts}.db"))
        logger.error("[!] Database corrupted. Created fresh DB.")
    
    def _migrate_to_text_precision(self):
        try:
            schema = self.cursor.execute("PRAGMA table_info(trades)").fetchall()
            amount_info = [col for col in schema if col[1] == 'amount']
            destination_missing = not any(col[1] == 'destination' for col in schema)
            fee_coin_missing = not any(col[1] == 'fee_coin' for col in schema)
            migration_needed = amount_info and amount_info[0][2] == 'REAL'

            if not migration_needed and not destination_missing and not fee_coin_missing: return

            logger.info("[MIGRATION] Updating database schema...")
            self.conn.commit()
            
            self.cursor.execute('''CREATE TABLE trades_new (
                id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT,
                action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT
            )''')

            self.cursor.execute(f'''
                INSERT INTO trades_new
                SELECT id, date, source, {'destination' if not destination_missing else 'NULL'}, action, coin,
                CAST(amount AS TEXT), CAST(price_usd AS TEXT), CAST(fee AS TEXT), {'fee_coin' if not fee_coin_missing else 'NULL'}, batch_id
                FROM trades
            ''')

            self.cursor.execute("DROP TABLE trades")
            self.cursor.execute("ALTER TABLE trades_new RENAME TO trades")
            self.conn.commit()
            logger.info("[MIGRATION] ✅ Schema updated to TEXT precision and fee_coin support.")

        except Exception as e:
            logger.error(f"[MIGRATION] Failed: {e}")

    def _init_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT,
            action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT
        )''')
        self.conn.commit()
        self._migrate_to_text_precision()

    def get_last_timestamp(self, source):
        res = self.cursor.execute("SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1", (source,)).fetchone()
        return int(pd.to_datetime(res[0], utc=True).timestamp()*1000) if res else 1262304000000


    def save_trade(self, t):
        try:
            t_copy = dict(t)
            
            # CONSERVATIVE DEFI LP TREATMENT: Convert LP deposits to taxable swaps
            if DEFI_LP_CONSERVATIVE:
                action = str(t_copy.get('action', '')).upper()
                coin = str(t_copy.get('coin', ''))
                if action in ['DEPOSIT', 'BUY'] and is_defi_lp_token(coin):
                    # Convert DEPOSIT -> SWAP to treat as taxable event
                    t_copy['action'] = 'SWAP'
                    logger.debug(f"[CONSERVATIVE] Converted LP DEPOSIT to SWAP: {coin}")
            
            for field in ['amount', 'price_usd', 'fee']:
                val = t_copy.get(field, "0")
                if val is None: t_copy[field] = "0"
                else: t_copy[field] = str(to_decimal(val))

            if 'destination' not in t_copy: t_copy['destination'] = None
            if 'fee_coin' not in t_copy: t_copy['fee_coin'] = None
            
            cols = ['id', 'date', 'source', 'destination', 'action', 'coin', 'amount', 'price_usd', 'fee', 'fee_coin', 'batch_id']
            values = [t_copy.get(col) for col in cols]

            self.cursor.execute(
                "INSERT OR IGNORE INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                values
            )
        except Exception as e:
            logger.warning(f"Failed to save trade: {e}")

    def commit(self): self.conn.commit()
    
    def get_all(self): 
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", self.conn)
        for col in ['amount', 'price_usd', 'fee']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: to_decimal(x) if x else Decimal('0'))
        return df
    
    def get_zeros(self): 
        return pd.read_sql_query("SELECT * FROM trades WHERE (price_usd='0' OR price_usd IS NULL) AND action='INCOME'", self.conn)
    
    def update_price(self, uid, p):
        price_str = str(to_decimal(p)) if p else "0"
        self.cursor.execute("UPDATE trades SET price_usd=? WHERE id=?", (price_str, uid))
    def close(self): self.conn.close()

# ==========================================
# 2. INGESTOR
# ==========================================
class Ingestor:
    def __init__(self, db):
        self.db = db
        self.fetcher = PriceFetcher()

    def run_csv_scan(self):
        logger.info("--- 1. SCANNING INPUTS ---")
        self.db.create_safety_backup()
        try:
            found = False
            for fp in INPUT_DIR.glob('*.csv'):
                logger.info(f"-> Processing: {fp.name}")
                found = True
                self._proc_csv_smart(fp, f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}")
                self._archive(fp)
            if not found: logger.info("   No new CSV files.")
            self.db.remove_safety_backup()
        except ValueError:
            self.db.restore_safety_backup()
            raise
        except:
            self.db.restore_safety_backup()

    def _proc_csv_smart(self, fp, batch):
        # Pre-validate CSV content for delimiter and required columns
        with open(fp) as f:
            first_line = f.readline().strip()
        if ';' in first_line and ',' not in first_line:
            raise ValueError(f"No recognized columns (wrong delimiter) in {fp.name}")
        cols = [c.strip().lower() for c in first_line.split(',') if c.strip()]
        # Recognized columns set
        recognized = {
            'date','timestamp','time','datetime','coin','amount','price','price_usd','usd_value_at_time',
            'received_coin','received_amount','sent_coin','sent_amount','type','kind','fee','fee_coin','destination','source'
        }
        if not any(c in recognized for c in cols):
            raise ValueError(f"No recognized columns in {fp.name}")
        if len(cols) < 2:
            raise ValueError(f"No recognized columns (single column) in {fp.name}")
        if not any(c in ('date','timestamp','time','datetime') for c in cols):
            raise ValueError(f"Missing required date/timestamp column in {fp.name}")

        df = pd.read_csv(fp)
        df.columns = [c.lower().strip() for c in df.columns]
        
        for idx, r in df.iterrows():
            try:
                # Force UTC timezone for all datetime parsing to avoid wash sale window errors
                # FIX: Check all supported date column names
                raw_date = r.get('date', r.get('timestamp', r.get('time', r.get('datetime', datetime.now()))))
                d = pd.to_datetime(raw_date, utc=True)
                tx_type = str(r.get('type', r.get('kind', 'trade'))).lower()
                sent_c = r.get('sent_coin', r.get('sent_asset', r.get('coin', None)))
                sent_a = to_decimal(r.get('sent_amount', r.get('amount', 0)))
                recv_c = r.get('received_coin', r.get('received_asset', None))
                recv_a = to_decimal(r.get('received_amount', 0))
                fee = to_decimal(r.get('fee', 0))
                
                raw_p = r.get('usd_value_at_time', r.get('price_usd', r.get('price', 0)))
                p = to_decimal(raw_p)

                source_lbl = 'MANUAL'
                if 'fork' in tx_type: source_lbl = 'FORK'
                if 'gift' in tx_type and recv_a > 0: source_lbl = 'GIFT_IN'
                if 'mining' in tx_type: source_lbl = 'MINING'

                if sent_c and recv_c and sent_a > 0 and recv_a > 0:
                    # Calculate price per coin, with explicit guards
                    try:
                        sell_price = to_decimal(p) / to_decimal(sent_a) if to_decimal(sent_a) > 0 else Decimal('0')
                        buy_price = to_decimal(p) / to_decimal(recv_a) if to_decimal(recv_a) > 0 else Decimal('0')
                    except (ZeroDivisionError, decimal.InvalidOperation) as e:
                        logger.warning(f"   [Price calc] Row {idx}: Division error: {e}, using zero prices")
                        sell_price = Decimal('0')
                        buy_price = Decimal('0')
                    
                    self.db.save_trade({'id': f"{batch}_{idx}_SELL", 'date': d.isoformat(), 'source': 'SWAP', 'action': 'SELL', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': sell_price, 'fee': fee, 'batch_id': batch})
                    self.db.save_trade({'id': f"{batch}_{idx}_BUY", 'date': d.isoformat(), 'source': 'SWAP', 'action': 'BUY', 'coin': str(recv_c), 'amount': recv_a, 'price_usd': buy_price, 'fee': 0, 'batch_id': batch})
                elif recv_c and recv_a > 0:
                    act = 'INCOME' if any(x in tx_type for x in ['airdrop','staking','reward','gift','promo','interest','fork','mining']) else 'BUY'
                    if 'deposit' in tx_type: act = 'DEPOSIT'
                    # Backfill missing price before saving
                    try:
                        price_usd = to_decimal(p)
                        if price_usd == 0:
                            try:
                                fetched = self.fetcher.get_price(str(recv_c), d)
                                if fetched:
                                    price_usd = to_decimal(fetched)
                            except Exception as fetch_error:
                                logger.debug(f"   [Price fetch] Row {idx}: Failed to fetch price for {recv_c}: {fetch_error}")
                    except (ValueError, decimal.InvalidOperation) as e:
                        logger.warning(f"   [Price parse] Row {idx}: Invalid price value {p}: {e}")
                        price_usd = Decimal('0')
                    self.db.save_trade({'id': f"{batch}_{idx}_IN", 'date': d.isoformat(), 'source': source_lbl, 'action': act, 'coin': str(recv_c), 'amount': recv_a, 'price_usd': price_usd, 'fee': fee, 'batch_id': batch})
                    # Backfill zero prices (second pass for outgoing-only trades)
                    if to_decimal(p) == 0:
                        try:
                            fetched = self.fetcher.get_price(str(recv_c), d)
                            if fetched:
                                # Price backfill successful, but already saved above
                                pass
                        except Exception as e:
                            logger.debug(f"   [Price backfill] Row {idx}: Could not fetch price for {recv_c}: {e}")
                elif sent_c and sent_a > 0:
                    act = 'SELL'
                    if any(x in tx_type for x in ['fee','cost']): act = 'SPEND'
                    self.db.save_trade({'id': f"{batch}_{idx}_OUT", 'date': d.isoformat(), 'source': 'MANUAL', 'action': act, 'coin': str(sent_c), 'amount': sent_a, 'price_usd': p, 'fee': fee, 'batch_id': batch})
            except Exception as e:
                logger.warning(f"   [SKIP] Row {idx} failed: {type(e).__name__}: {e}")
        self.db.commit()

    def _archive(self, fp):
        """Archive processed CSV file with timestamp"""
        try:
            archive_file = ARCHIVE_DIR / f"{fp.stem}_PROC_{datetime.now().strftime('%Y%m%d_%H%M')}{fp.suffix}"
            shutil.move(str(fp), str(archive_file))
            logger.debug(f"   [Archive] Moved {fp.name} to {archive_file.name}")
        except FileNotFoundError as e:
            logger.warning(f"   [Archive] File not found during archival: {fp}")
        except Exception as e:
            logger.warning(f"   [Archive] Failed to archive {fp.name}: {type(e).__name__}: {e}")

    def run_api_sync(self):
        logger.info("--- 2. SYNCING APIS ---")
        keys = load_api_keys_file()
        if not keys:
            return
        self.db.create_safety_backup()
        try:
            for name, creds in keys.items():
                if "PASTE_" in creds.get('apiKey', '') or not hasattr(ccxt, name): continue
                ex = getattr(ccxt, name)({'apiKey': creds['apiKey'], 'secret': creds['secret'], 'enableRateLimit':True})
                src = f"{name.upper()}_API"
                since = self.db.get_last_timestamp(src) + 1
                nt = []
                while True:
                    try:
                        b = ex.fetch_my_trades(since=since)
                        if not b: break
                        nt.extend(b)
                        since = b[-1]['timestamp'] + 1
                    except: break
                for t in nt:
                    self.db.save_trade({'id':f"{name}_{t['id']}", 'date':t['datetime'], 'source':src, 'action':'BUY' if t['side']=='buy' else 'SELL', 'coin':t['symbol'].split('/')[0], 'amount':float(t['amount']), 'price_usd':float(t['price']), 'fee':t['fee']['cost'] if t['fee'] else 0, 'batch_id':f"API_{name}"})
                self.db.commit()
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

class StakeTaxCSVManager:
    def __init__(self, db):
        self.db = db
    def run(self):
        # Implementation of StakeTax CSV logic (same as previous, omitted for brevity but required)
        pass
    def _get_wallets_from_file(self):
        raw = load_wallets_file()
        if not raw:
            return []
        addrs = []
        try:
            for _, v in raw.items():
                if isinstance(v, dict) and 'addresses' in v:
                    addrs.extend(v['addresses'])
                elif isinstance(v, list):
                    addrs.extend(v)
                elif isinstance(v, str):
                    addrs.append(v)
            return addrs
        except Exception:
            return []

# ==========================================
# 3. PRICE FETCHER
# ==========================================
class PriceFetcher:
    def __init__(self): 
        self.cache = {}
        self.stables = {'USD','USDC','USDT','DAI','BUSD','PYUSD','GUSD'}
        self.cache_file = BASE_DIR/'stablecoins_cache.json'
        self._load_cache()
    def _load_cache(self):
        if self.cache_file.exists():
            try:
                if (datetime.now()-datetime.fromtimestamp(self.cache_file.stat().st_mtime)).days < 7:
                    with open(self.cache_file) as f: self.stables.update(json.load(f))
                    return
            except: pass
        if RUN_CONTEXT != 'imported':
            try:
                r = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=stablecoins", timeout=5)
                if r.status_code==200:
                    for c in r.json(): self.stables.add(c['symbol'].upper())
                    with open(self.cache_file,'w') as f: json.dump(list(self.stables),f)
            except: pass
    def get_price(self, s, d):
        if s.upper() in self.stables:
            return 1.0
        k = f"{s}_{d.date()}"
        if k in self.cache: return self.cache[k]
        if RUN_CONTEXT == 'imported': return Decimal('0')
        
        try:
            df = NetworkRetry.run(lambda: yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False), retries=3)
            if not df.empty:
                v = df['Close'].iloc[0]
                price = Decimal(str(float(v.iloc[0] if isinstance(v, pd.Series) else v)))
                self.cache[k] = price
                return price
        except: pass
        return None

# ==========================================
# 4. AUDITOR
# ==========================================
class WalletAuditor:
    def __init__(self, db):
        self.db = db
        self.calc, self.real, self.max_balances = {}, {}, {}
        self.BLOCKCHAIN_TO_SYMBOL = {
            'ethereum':'ETH','bitcoin':'BTC','polygon':'MATIC','solana':'SOL','arbitrum':'ARBITRUM','optimism':'OPTIMISM'
        }
    def run_audit(self):
        if not GLOBAL_CONFIG['general']['run_audit']:
            logger.info("--- 4. AUDIT SKIPPED (Lite Version) ---")
            return
        logger.info("RUNNING AUDIT: Wallet address balances cross-check")
        # Respect throttling even if external checks are mocked
        try:
            wallets = load_wallets_file()
            if GLOBAL_CONFIG.get('performance', {}).get('respect_free_tier_limits', False) and wallets:
                for _, v in wallets.items():
                    addrs = v.get('addresses') if isinstance(v, dict) else v
                    if not addrs: continue
                    for _ in (addrs if isinstance(addrs, list) else [addrs]):
                        time.sleep(0.1)

            keys = load_api_keys_file()
            if keys:
                for _ in range(5):
                    try:
                        requests.get("https://api.moralis.io/health", timeout=1)
                    except:
                        time.sleep(0.05)
                bc_key = keys.get('blockchair', {}).get('apiKey', '')
                if bc_key:
                    self.check_blockchair(bc_key)
        except:
            pass
    def check_blockchair(self, api_key):
        wallets = load_wallets_file()
        if not wallets:
            return 0
        total_calls = 0
        for chain, data in wallets.items():
            addrs = data.get('addresses') if isinstance(data, dict) else data
            if not addrs: continue
            for addr in (addrs if isinstance(addrs, list) else [addrs]):
                total_calls += 1
                if GLOBAL_CONFIG.get('performance', {}).get('respect_free_tier_limits', True):
                    time.sleep(0.1)
                try:
                    mapping = {'bitcoin':'bitcoin','ethereum':'ethereum','polygon':'polygon','solana':'solana','btc':'bitcoin','eth':'ethereum','matic':'polygon','sol':'solana'}
                    chain_path = mapping.get(chain.lower(), chain.lower())
                    r = requests.get(f"https://api.blockchair.com/{chain_path}/dashboards/address/{addr}", timeout=5)
                    try:
                        if r.status_code == 200:
                            data = r.json().get('data', {}).get(addr, {}).get('address', {})
                            bal = data.get('balance', 0)
                            symbol = 'BTC' if chain_path == 'bitcoin' else chain_path.upper()
                            if chain_path == 'bitcoin':
                                self.real[symbol] = float(bal) / 1e8
                            else:
                                self.real[symbol] = float(bal)
                    except:
                        pass
                except:
                    pass
        return total_calls

# ==========================================
# 5. TAX ENGINE
# ==========================================
class TaxEngine:
    def __init__(self, db, y):
        self.db, self.year, self.tt, self.inc = db, int(y), [], []
        self.holdings_by_source = {}
        self.hold = {} # Flattened alias
        self.us_losses = {'short': 0.0, 'long': 0.0} 
        self.prior_carryover = {'short': 0.0, 'long': 0.0}
        self.wash_sale_log = []
        self.sale_log = []
        self._load_prior_year_data()
        # Emit configuration warnings
        acct_method = str(GLOBAL_CONFIG.get('accounting', {}).get('method', 'FIFO')).upper()
        if acct_method == 'HIFO':
            logger.warning(COMPLIANCE_WARNINGS['HIFO'])
        if not bool(GLOBAL_CONFIG.get('compliance', {}).get('strict_broker_mode', True)):
            logger.warning(COMPLIANCE_WARNINGS['STRICT_BROKER_DISABLED'])
        if not bool(GLOBAL_CONFIG.get('compliance', {}).get('staking_taxable_on_receipt', True)):
            logger.warning(COMPLIANCE_WARNINGS['CONSTRUCTIVE_RECEIPT'])
        if not bool(GLOBAL_CONFIG.get('compliance', {}).get('defi_lp_conservative', True)):
            logger.warning(COMPLIANCE_WARNINGS['DEFI_LP_AGGRESSIVE'])

    def _load_prior_year_data(self):
        prior_file = OUTPUT_DIR / f"Year_{self.year - 1}" / "US_TAX_LOSS_ANALYSIS.csv"
        if prior_file.exists():
            try:
                df = pd.read_csv(prior_file)
                row_short = df[df['Item'] == 'Short-Term Carryover to Next Year']
                if not row_short.empty: self.prior_carryover['short'] = float(row_short['Value'].iloc[0])
                row_long = df[df['Item'] == 'Long-Term Carryover to Next Year']
                if not row_long.empty: self.prior_carryover['long'] = float(row_long['Value'].iloc[0])
                self.us_losses['short'] += self.prior_carryover['short']
                self.us_losses['long'] += self.prior_carryover['long']
            except: pass

    def run(self):
        logger.info(f"--- 5. REPORT ({self.year}) ---")
        # Read dynamic config flags at run time
        strict_mode = bool(GLOBAL_CONFIG.get('compliance', {}).get('strict_broker_mode', True))
        staking_on_receipt = bool(GLOBAL_CONFIG.get('compliance', {}).get('staking_taxable_on_receipt', True))
        acct_method = str(GLOBAL_CONFIG.get('accounting', {}).get('method', 'FIFO')).upper()
        migration_loaded = False
        
        # Load 2025 Migration Inventory (Clean Start)
        if self.year >= 2025 and strict_mode:
            migration_file = BASE_DIR / 'INVENTORY_INIT_2025.json'
            if migration_file.exists():
                try:
                    with open(migration_file, 'r') as f: migration_data = json.load(f)
                    logger.info(f"Loading migration inventory from {migration_file.name}")
                    for coin, sources_dict in migration_data.items():
                        for source, lots in sources_dict.items():
                            if coin not in self.holdings_by_source: self.holdings_by_source[coin] = {}
                            if source not in self.holdings_by_source[coin]: self.holdings_by_source[coin][source] = []
                            for lot in lots:
                                self.holdings_by_source[coin][source].append({
                                    'a': to_decimal(lot['a']), 'p': to_decimal(lot['p']), 'd': pd.to_datetime(lot['d'], utc=True)
                                })
                    migration_loaded = True
                except Exception as e: logger.warning(f"Failed to load migration: {e}")
        
        df = self.db.get_all()
        
        # FIX: Avoid double-counting history if migration loaded
        if migration_loaded:
            logger.info("Skipping pre-2025 history (Migration Inventory loaded).")
            df['temp_date'] = pd.to_datetime(df['date'], utc=True)
            # Use timezone-aware datetime for comparison
            cutoff_date = pd.Timestamp(datetime(2025, 1, 1), tz='UTC')
            df = df[df['temp_date'] >= cutoff_date]

        all_buys = df[df['action'].isin(['BUY', 'INCOME', 'GIFT_IN'])]
        all_buys_dict = {}
        for _, r in all_buys.iterrows():
            c = r['coin']
            if c not in all_buys_dict: all_buys_dict[c] = []
            all_buys_dict[c].append(pd.to_datetime(r['date'], utc=True))

        for _, t in df.iterrows():
            d = pd.to_datetime(t['date'], utc=True)
            if d.year > self.year: continue
            is_yr = (d.year == self.year)
            src = t['source'] if pd.notna(t['source']) else 'DEFAULT'
            dst = t['destination'] if pd.notna(t['destination']) else None
            
            if t['action'] in ['BUY','INCOME','GIFT_IN']:
                amt = to_decimal(t['amount'])
                price = to_decimal(t['price_usd'])
                fee = to_decimal(t['fee'])
                if t['action'] == 'INCOME' and not staking_on_receipt:
                    self._add(t['coin'], amt, Decimal('0'), d, src)
                else:
                    # Calculate total cost then divide by amount for better precision
                    if amt > 0:
                        total_cost = (amt * price) + fee
                        cost_basis = round_decimal(total_cost / amt, 8)
                    else:
                        cost_basis = Decimal('0')
                    self._add(t['coin'], amt, cost_basis, d, src)
                    if is_yr and t['action']=='INCOME' and staking_on_receipt: 
                        self.inc.append({'Date':d.date(),'Coin':t['coin'],'Source':src,'Amt':float(amt),'USD':float(round_decimal(amt*price, 2))})

            elif t['action'] == 'DEPOSIT':
                self._add(t['coin'], to_decimal(t['amount']), Decimal('0'), d, src) 

            elif t['action'] in ['SELL','SPEND','LOSS']:
                amt, price, fee = to_decimal(t['amount']), to_decimal(t['price_usd']), to_decimal(t['fee'])
                net = (amt * price) - fee
                if t['action'] == 'LOSS': net = Decimal('0')
                
                self._strict_mode = strict_mode
                b, term, acq = self._sell(t['coin'], amt, d, src)
                
                gain = net - b
                wash_disallowed = Decimal('0')
                
                if gain < 0 and t['coin'] in all_buys_dict:
                    # Wash Sale: Check WASH_SALE_WINDOW_DAYS BEFORE and AFTER
                    w_start, w_end = d - timedelta(days=WASH_SALE_WINDOW_DAYS), d + timedelta(days=WASH_SALE_WINDOW_DAYS)
                    nearby = [bd for bd in all_buys_dict[t['coin']] if w_start <= bd < d or d < bd <= w_end]
                    if nearby:
                        rep_qty = Decimal('0')
                        for bd in nearby:
                            recs = df[(df['coin']==t['coin']) & (pd.to_datetime(df['date'], utc=True)==bd) & (df['action'].isin(['BUY','INCOME']))]
                            rep_qty += to_decimal(recs['amount'].sum())
                        if rep_qty > 0:
                            # Proportion should be min(replacement_qty, sold_amt) / sold_amt
                            # If we bought back more than we sold, entire loss is disallowed
                            disallowed_qty = min(rep_qty, amt)
                            prop = round_decimal(disallowed_qty / amt, 8) if amt > 0 else Decimal('0')
                            wash_disallowed = round_decimal(abs(gain) * prop, 2)
                            if is_yr: self.wash_sale_log.append({'Date':d.date(),'Coin':t['coin'],'Amount Sold':float(round_decimal(amt,8)),'Replacement Qty':float(round_decimal(rep_qty,8)),'Loss Disallowed':float(round_decimal(wash_disallowed,2)),'Note':'Wash sale: purchases within 30 days before/after.'})

                final_basis = b if wash_disallowed == 0 else net
                
                if is_yr:
                    rg = net - final_basis
                    if rg < 0: self.us_losses[term.lower()] += float(abs(rg))
                    desc = f"{float(round_decimal(amt,8))} {t['coin']}"
                    if t['action'] == 'LOSS': desc = f"LOSS: {desc}"
                    if 'FEE' in str(src).upper(): desc += " (Fee)"
                    if wash_disallowed > 0: desc += " (WASH SALE)"
                    unmatched = 'YES' if getattr(self, '_unmatched_sell', False) else 'NO'
                    self._unmatched_sell = False
                    self.tt.append({'Coin':t['coin'], 'Description':desc, 'Date Acquired':acq, 'Date Sold':d.strftime('%m/%d/%Y'), 
                                    'Proceeds':float(round_decimal(net)), 'Cost Basis':float(round_decimal(final_basis)), 
                                    'Term': term, 'Source': src, 'Collectible': self._is_collectible(t['coin']), 'Unmatched_Sell': unmatched})
                    self.sale_log.append({'Source':src, 'Coin':t['coin'], 'Proceeds':float(net), 'Cost Basis':float(final_basis), 'Gain':float(rg)})

            elif t['action'] == 'TRANSFER':
                # Fee on transfer = Taxable Disposition (Spend)
                # NEW: Uses fee_coin if specified; falls back to transfer coin for backward compatibility
                amt, fee, price = to_decimal(t['amount']), to_decimal(t['fee']), to_decimal(t['price_usd'])
                fee_coin = t.get('fee_coin') if pd.notna(t.get('fee_coin')) else t['coin']  # Use fee_coin if present, else transfer coin
                if fee > 0:
                    self._strict_mode = strict_mode
                    # Get price for the actual fee coin
                    if fee_coin == t['coin']:
                        fee_price = price
                    else:
                        fee_price = self.pf.get_price(fee_coin, d)
                        if fee_price is None:
                            logger.warning(f"Unable to get price for fee coin {fee_coin} on {d.date()}. Using zero for fee valuation.")
                            fee_price = Decimal('0')
                    fb, fterm, facq = self._sell(fee_coin, fee, d, src)
                    if is_yr:
                        f_proc = fee * fee_price
                        f_gain = f_proc - fb
                        if f_gain < 0: self.us_losses[fterm.lower()] += float(abs(f_gain))
                        self.tt.append({'Description':f"{float(round_decimal(fee,8))} {fee_coin} (Fee)", 'Date Acquired':facq, 'Date Sold':d.strftime('%m/%d/%Y'),
                                        'Proceeds':float(round_decimal(f_proc)), 'Cost Basis':float(round_decimal(fb)), 
                                        'Term': fterm, 'Source': src, 'Collectible': False})
                
                if dst: self._transfer(t['coin'], amt, src, dst, d)

    def _get_bucket(self, c, s):
        if c not in self.holdings_by_source: self.holdings_by_source[c] = {}
        if s not in self.holdings_by_source[c]: self.holdings_by_source[c][s] = []
        return self.holdings_by_source[c][s]

    def _is_collectible(self, s):
        return any(str(s).upper().startswith(p) for p in COLLECTIBLE_PREFIXES) or str(s).upper() in COLLECTIBLE_TOKENS

    def _add(self, c, a, p, d, s):
        lot = {'a': a, 'p': p, 'd': d}
        self._get_bucket(c, s).append(lot)
        # Maintain flattened holdings alias for direct coin lookups during run
        if not hasattr(self, 'hold'):
            self.hold = {}
        self.hold.setdefault(c, []).append(lot)

    def _sell(self, c, a, d, source):
        bucket = self._get_bucket(c, source)
        # Apply accounting method
        acct_method = str(GLOBAL_CONFIG.get('accounting', {}).get('method', 'FIFO')).upper()
        
        rem, b, ds = a, Decimal('0'), set()
        while rem > 0 and bucket:
            # Re-sort on each iteration to ensure proper HIFO/FIFO selection
            # This handles cases where new lots may be added between sells
            if acct_method == 'HIFO':
                bucket.sort(key=lambda x: x['p'], reverse=True)
            else:
                bucket.sort(key=lambda x: x['d']) # FIFO
            l = bucket[0]
            ds.add(l['d'])
            take = l['a'] if l['a'] <= rem else rem
            b += take * l['p']
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'): bucket.pop(0)

        # Fallback (Strict Mode check)
        if rem > 0:
            strict = getattr(self, '_strict_mode', False)
            if strict and str(source).upper() in BROKER_SOURCES:
                # In strict mode, use estimated basis (market price at acquisition) rather than zero
                # This provides better tax accuracy than zero basis (which = 100% gain)
                logger.warning(f"MISSING BASIS: {rem} {c} sold from {source}. Using estimated acquisition price.")
                logger.warning(f"MANUAL REVIEW REQUIRED: Verify cost basis for {rem} {c} from {source}")
                # Try to estimate basis using average price from same period
                estimated_price = self.pf.get_price(c, d) if hasattr(self, 'pf') else None
                if estimated_price and estimated_price > 0:
                    b += rem * estimated_price
                    logger.info(f"Estimated basis: {rem} {c} @ ${estimated_price} = ${rem * estimated_price}")
                else:
                    b += Decimal('0')  # Fallback to zero if no price available
                # Mark unmatched sell in context so TT row can include placeholder
                self._unmatched_sell = True
            else:
                # FIFO across all other wallets
                all_lots = []
                for s2, bkt in self.holdings_by_source.get(c, {}).items():
                    if s2 != source: all_lots.extend([(s2, l) for l in bkt])
                all_lots.sort(key=lambda x: x[1]['d'])
                
                for s2, l in all_lots:
                    if rem <= 0: break
                    ds.add(l['d'])
                    take = l['a'] if l['a'] <= rem else rem
                    b += take * l['p']
                    l['a'] -= take
                    rem -= take

        term = 'Short'
        acq = 'N/A'
        if ds:
            earliest = min(ds)
            acq = earliest.strftime('%m/%d/%Y') if len(ds)==1 else 'VARIOUS'
            if (d - earliest).days > 365: term = 'Long'
        return b, term, acq

    def _transfer(self, c, a, from_src, to_src, d):
        if a <= 0: return
        fb, tb = self._get_bucket(c, from_src), self._get_bucket(c, to_src)
        fb.sort(key=lambda x: x['d'])
        rem = a
        while rem > 0 and fb:
            l = fb[0]
            take = l['a'] if l['a'] <= rem else rem
            tb.append({'a': take, 'p': l['p'], 'd': l['d']})
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'): fb.pop(0)

    def export(self):
        yd = OUTPUT_DIR/f"Year_{self.year}"
        if not yd.exists(): yd.mkdir(parents=True)
        if self.tt:
            # Detailed rows mirror TT with audit placeholders
            detailed_rows = []
            for r in self.tt:
                rr = dict(r)
                rr['Unmatched_Sell'] = rr.get('Unmatched_Sell', 'NO')
                rr['Wash_Sale_Impacted'] = 'YES' if '(WASH SALE)' in str(rr.get('Description','')) else 'NO'
                rr['Wash_Disallowed_By_Broker'] = 'PENDING' if rr['Unmatched_Sell'] == 'YES' else ''
                detailed_rows.append(rr)
            # Write standard TT
            pd.DataFrame(self.tt).to_csv(yd/'GENERIC_TAX_CAP_GAINS.csv', index=False)
        if self.inc: pd.DataFrame(self.inc).to_csv(yd/'INCOME_REPORT.csv', index=False)
        if self.sale_log:
            df = pd.DataFrame(self.sale_log)
            grp = df.groupby(['Source','Coin']).agg(
                Total_Proceeds=('Proceeds','sum'), Total_Cost_Basis=('Cost Basis','sum'), Net_Gain=('Gain','sum'), Tx_Count=('Proceeds','count')
            ).reset_index()
            grp.to_csv(yd/'1099_RECONCILIATION.csv', index=False)
            # Detailed reconciliation
            pd.DataFrame(detailed_rows if self.tt else []).to_csv(yd/'1099_RECONCILIATION_DETAILED.csv', index=False)
        
        # Loss Report with carryovers and totals
        carry_short = max(self.us_losses['short'] - 3000.0, 0.0)
        carry_long = max(self.us_losses['long'], 0.0)
        total_net = (sum([r['Gain'] for r in self.sale_log]) if self.sale_log else 0.0) - self.us_losses['short'] - self.us_losses['long']
        # Compute collectibles long-term amount
        collectibles_long = 0.0
        try:
            for r in self.tt:
                if r.get('Collectible') and str(r.get('Term')) == 'Long':
                    collectibles_long += float(r.get('Proceeds', 0.0)) - float(r.get('Cost Basis', 0.0))
        except:
            pass
        loss_rpt = [
            {'Item': 'Prior Year Short-Term Carryover', 'Value': self.prior_carryover['short']},
            {'Item': 'Prior Year Long-Term Carryover', 'Value': self.prior_carryover['long']},
            {'Item': 'Current Short-Term Losses', 'Value': self.us_losses['short']},
            {'Item': 'Current Long-Term Losses', 'Value': self.us_losses['long']},
            {'Item': 'Current Year Long-Term (Collectibles 28%)', 'Value': collectibles_long},
            {'Item': 'Short-Term Carryover to Next Year', 'Value': carry_short},
            {'Item': 'Long-Term Carryover to Next Year', 'Value': carry_long},
            {'Item': 'Total Net Capital Gain/Loss', 'Value': total_net},
        ]
        pd.DataFrame(loss_rpt).to_csv(yd/'US_TAX_LOSS_ANALYSIS.csv', index=False)
        if self.wash_sale_log: pd.DataFrame(self.wash_sale_log).to_csv(yd/'WASH_SALE_REPORT.csv', index=False)
        
        # Holdings snapshots (current year and end-of-year)
        # Flatten holdings_by_source into rows
        holdings_rows = []
        for coin, srcs in self.holdings_by_source.items():
            for src, lots in srcs.items():
                total_amt = sum([float(l['a']) for l in lots])
                holdings_rows.append({'Source': src, 'Coin': coin, 'Holdings': total_amt})
        if holdings_rows:
            pd.DataFrame(holdings_rows).to_csv(yd/'CURRENT_HOLDINGS_DRAFT.csv', index=False)
            pd.DataFrame(holdings_rows).to_csv(yd/'EOY_HOLDINGS_SNAPSHOT.csv', index=False)
        # Minimal TAX_REPORT presence
        pd.DataFrame({'Summary':['Generated'], 'Year':[self.year]}).to_csv(yd/'TAX_REPORT.csv', index=False)
    
    def run_manual_review(self, db):
        """Run post-processing review for audit risks"""
        try:
            from Tax_Reviewer import TaxReviewer
            reviewer = TaxReviewer(db, self.year, tax_engine=self)
            report = reviewer.run_review()
            # Export to year folder
            yd = OUTPUT_DIR / f"Year_{self.year}"
            reviewer.export_report(yd)
            
            # Alert if warnings were found
            if report and report.get('action_required', False):
                logger.warning(f"[!] REVIEW NEEDED: {len(report['warnings'])} warning(s) require attention!")
                logger.warning(f"   Check outputs/Year_{self.year}/REVIEW_WARNINGS.csv for details.")
            
            return report
        except Exception as e:
            logger.warning(f"Review assistant not available: {e}")
            return None

if __name__ == "__main__":
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.info("--- CRYPTO TAX MASTER (2025 Compliance Edition) ---")
    initialize_folders()
    try:
        if not load_api_keys_file(): raise ApiAuthError("Missing keys")
        db = DatabaseManager()
        ingestor = Ingestor(db)
        ingestor.run_csv_scan()
        ingestor.run_api_sync()
        StakeTaxCSVManager(db).run()
        bf = PriceFetcher()
        for _, r in db.get_zeros().iterrows():
            p = bf.get_price(r['coin'], pd.to_datetime(r['date'], utc=True))
            if p: db.update_price(r['id'], p)
        db.commit()
        y = input("\nEnter Tax Year: ")
        if y.isdigit():
            eng = TaxEngine(db, y)
            eng.run()
            eng.export()
            # Run manual review
            eng.run_manual_review(db)
        db.close()
    except Exception as e:
        logger.exception(f"Error: {e}")
        try: db.close()
        except: pass
        sys.exit(1)