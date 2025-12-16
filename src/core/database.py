"""
Database Management Module

Provides database operations for the tax calculation engine:
- SQLite connection management
- Trade transaction CRUD operations
- Schema migrations and integrity checks
- Backup and restore functionality
"""

import sqlite3
import shutil
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from decimal import Decimal

from src.utils.constants import DB_FILE, BASE_DIR
from src.utils.config import load_config

logger = logging.getLogger("crypto_tax_engine")

# Load global config
GLOBAL_CONFIG = load_config()

# ====================================================================================
# UTILITY FUNCTION IMPORTS
# ====================================================================================
# These will be imported from main engine to avoid circular dependencies
_to_decimal = None
_is_defi_lp_token = None
_DEFI_LP_CONSERVATIVE = True
_initialize_folders = None


def set_utility_functions(to_decimal_func, is_defi_lp_token_func, defi_lp_conservative, initialize_folders_func):
    """
    Set utility functions from main engine to avoid circular imports.
    Called during engine initialization.
    """
    global _to_decimal, _is_defi_lp_token, _DEFI_LP_CONSERVATIVE, _initialize_folders
    _to_decimal = to_decimal_func
    _is_defi_lp_token = is_defi_lp_token_func
    _DEFI_LP_CONSERVATIVE = defi_lp_conservative
    _initialize_folders = initialize_folders_func


def to_decimal(value):
    """Wrapper for decimal conversion utility."""
    if _to_decimal is not None:
        return _to_decimal(value)
    # Fallback implementation
    if value is None:
        return Decimal('0')
    try:
        return Decimal(str(value))
    except:
        return Decimal('0')


def is_defi_lp_token(coin):
    """Wrapper for DeFi LP token detection."""
    if _is_defi_lp_token is not None:
        return _is_defi_lp_token(coin)
    return False


def initialize_folders():
    """Wrapper for folder initialization."""
    if _initialize_folders is not None:
        _initialize_folders()


@property
def DEFI_LP_CONSERVATIVE():
    """Get DeFi LP conservative mode setting."""
    return _DEFI_LP_CONSERVATIVE


# ====================================================================================
# DATABASE MANAGER
# ====================================================================================

class DatabaseManager:
    """
    Manages SQLite database operations for trade transactions.
    
    Features:
    - Automatic schema migrations
    - Integrity checking and recovery
    - Backup/restore functionality
    - Decimal precision handling (TEXT-based storage)
    - Support for cross-wallet transfers
    """
    
    def __init__(self):
        """Initialize database connection and ensure schema is up to date."""
        initialize_folders()
        self._ensure_integrity()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _backup_path(self):
        """Get path for safety backup file."""
        return DB_FILE.with_suffix('.bak')

    def create_safety_backup(self):
        """
        Create a safety backup of the database before destructive operations.
        Only creates backup if enabled in config.
        """
        if not GLOBAL_CONFIG['general']['create_db_backups']:
            return
        if DB_FILE.exists():
            self.conn.commit()
            try:
                shutil.copy(DB_FILE, self._backup_path())
            except Exception as e:
                logger.warning(f"Failed to create safety backup: {e}")

    def restore_safety_backup(self):
        """
        Restore database from safety backup.
        Used for rollback after failed operations.
        """
        if not GLOBAL_CONFIG['general']['create_db_backups']:
            return
        backup_path = self._backup_path()
        if backup_path.exists():
            self.close()
            try:
                shutil.copy(backup_path, DB_FILE)
                self.conn = sqlite3.connect(str(DB_FILE))
                self.cursor = self.conn.cursor()
                logger.info("[SAFE] Restored database backup.")
            except Exception as e:
                logger.error(f"Failed to restore backup: {e}")

    def remove_safety_backup(self):
        """Remove safety backup after successful operation."""
        pass  # Kept for backward compatibility

    def _ensure_integrity(self):
        """
        Check database integrity before opening.
        Recovers corrupted database by moving it aside and starting fresh.
        """
        if not DB_FILE.exists():
            return
        conn = None
        try:
            conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
            conn.execute("PRAGMA integrity_check")
            conn.close()
        except Exception as e:
            try:
                if conn:
                    conn.close()
            finally:
                self._recover_db()

    def _recover_db(self):
        """
        Recover from corrupted database by moving it aside.
        Creates a fresh database for new transactions.
        """
        timestamp = datetime.now().strftime("%Y%m%d")
        corrupt_path = BASE_DIR / f"CORRUPT_{timestamp}.db"
        shutil.move(str(DB_FILE), str(corrupt_path))
        logger.error(f"[!] Database corrupted. Moved to {corrupt_path}. Created fresh DB.")
    
    def _migrate_to_text_precision(self):
        """
        Migrate old REAL-based columns to TEXT for decimal precision.
        Also adds missing columns (destination, fee_coin) if needed.
        
        This migration ensures:
        - No floating-point precision loss
        - Support for cross-wallet transfers (destination column)
        - Support for different fee coins (fee_coin column)
        """
        try:
            schema = self.cursor.execute("PRAGMA table_info(trades)").fetchall()
            amount_info = [col for col in schema if col[1] == 'amount']
            destination_missing = not any(col[1] == 'destination' for col in schema)
            fee_coin_missing = not any(col[1] == 'fee_coin' for col in schema)
            migration_needed = amount_info and amount_info[0][2] == 'REAL'

            if not migration_needed and not destination_missing and not fee_coin_missing:
                return

            logger.info("[MIGRATION] Updating database schema...")
            self.conn.commit()
            
            # Create new table with correct schema
            self.cursor.execute('''CREATE TABLE trades_new (
                id TEXT PRIMARY KEY,
                date TEXT,
                source TEXT,
                destination TEXT,
                action TEXT,
                coin TEXT,
                amount TEXT,
                price_usd TEXT,
                fee TEXT,
                fee_coin TEXT,
                batch_id TEXT
            )''')

            # Copy data with type conversion
            self.cursor.execute(f'''
                INSERT INTO trades_new
                SELECT id, date, source,
                {'destination' if not destination_missing else 'NULL'},
                action, coin,
                CAST(amount AS TEXT),
                CAST(price_usd AS TEXT),
                CAST(fee AS TEXT),
                {'fee_coin' if not fee_coin_missing else 'NULL'},
                batch_id
                FROM trades
            ''')

            # Replace old table
            self.cursor.execute("DROP TABLE trades")
            self.cursor.execute("ALTER TABLE trades_new RENAME TO trades")
            self.conn.commit()
            logger.info("[MIGRATION] ✅ Schema updated to TEXT precision and fee_coin support.")

        except Exception as e:
            logger.error(f"[MIGRATION] Failed: {e}")

    def _init_tables(self):
        """
        Initialize database tables with current schema.
        Runs migrations if existing table has old schema.
        """
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            date TEXT,
            source TEXT,
            destination TEXT,
            action TEXT,
            coin TEXT,
            amount TEXT,
            price_usd TEXT,
            fee TEXT,
            fee_coin TEXT,
            batch_id TEXT
        )''')
        self.conn.commit()
        self._migrate_to_text_precision()

    def get_last_timestamp(self, source):
        """
        Get the timestamp of the most recent transaction from a given source.
        Used for incremental API syncing.
        
        Args:
            source: Source identifier (e.g., 'BINANCE', 'COINBASE')
            
        Returns:
            Unix timestamp in milliseconds, or 1262304000000 (Jan 1, 2010) if no trades
        """
        res = self.cursor.execute(
            "SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1",
            (source,)
        ).fetchone()
        return int(pd.to_datetime(res[0], utc=True).timestamp() * 1000) if res else 1262304000000

    def save_trade(self, t):
        """
        Save a trade transaction to the database.
        
        Features:
        - Automatic decimal conversion
        - DeFi LP token handling (conservative treatment)
        - Duplicate detection (INSERT OR IGNORE)
        - Missing field defaults
        
        Args:
            t: Trade dictionary with keys: id, date, source, action, coin, amount, price_usd, fee, etc.
        """
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
            
            # Convert numeric fields to decimal strings
            for field in ['amount', 'price_usd', 'fee']:
                val = t_copy.get(field, "0")
                if val is None:
                    t_copy[field] = "0"
                else:
                    t_copy[field] = str(to_decimal(val))

            # Set defaults for optional fields
            if 'destination' not in t_copy:
                t_copy['destination'] = None
            if 'fee_coin' not in t_copy:
                t_copy['fee_coin'] = None
            
            # Insert trade (ignore duplicates)
            cols = ['id', 'date', 'source', 'destination', 'action', 'coin', 
                    'amount', 'price_usd', 'fee', 'fee_coin', 'batch_id']
            values = [t_copy.get(col) for col in cols]

            self.cursor.execute(
                """INSERT OR IGNORE INTO trades 
                (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                values
            )
        except Exception as e:
            logger.warning(f"Failed to save trade: {e}")

    def commit(self):
        """Commit pending transactions to database."""
        self.conn.commit()
    
    def get_all(self):
        """
        Retrieve all trades from database.
        
        Returns:
            DataFrame with all trades, sorted by date ascending.
            Numeric columns are converted to Decimal for precision.
        """
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", self.conn)
        for col in ['amount', 'price_usd', 'fee']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: to_decimal(x) if x else Decimal('0'))
        return df
    
    def get_zeros(self):
        """
        Get income transactions with missing or zero prices.
        Used to identify transactions that need price lookups.
        
        Returns:
            DataFrame of income transactions with missing prices
        """
        return pd.read_sql_query(
            "SELECT * FROM trades WHERE (price_usd='0' OR price_usd IS NULL) AND action='INCOME'",
            self.conn
        )
    
    def update_price(self, uid, price):
        """
        Update the USD price for a specific transaction.
        
        Args:
            uid: Transaction ID
            price: New price in USD (Decimal or convertible to Decimal)
        """
        price_str = str(to_decimal(price)) if price else "0"
        self.cursor.execute("UPDATE trades SET price_usd=? WHERE id=?", (price_str, uid))
    
    def close(self):
        """Close database connection."""
        self.conn.close()
