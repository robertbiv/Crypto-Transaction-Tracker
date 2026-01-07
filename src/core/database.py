"""
================================================================================
DATABASE MANAGER - SQLite Transaction Database
================================================================================

Manages all database operations for cryptocurrency trade transactions.

Core Responsibilities:
    - SQLite connection lifecycle management
    - Transaction CRUD (Create, Read, Update, Delete) operations
    - Automatic schema migrations and versioning
    - Database integrity checking and corruption recovery
    - Backup and restore functionality
    - Batch operations for performance

Data Model:
    - Trades table: All buy/sell/transfer/income transactions
    - Decimal precision handling (TEXT storage for accuracy)
    - UTC timestamp normalization
    - Source/destination tracking for transfers
    - Batch ID for atomic multi-leg transactions

Features:
    - Automatic schema updates for new columns
    - Safety backups before destructive operations
    - DeFi LP token special handling
    - Duplicate detection and prevention
    - Query optimization for large datasets

Integration:
    - Used by TransactionEngine for Transaction calculations
    - Used by Ingestor for data import
    - Used by Web UI for transaction management
    - Test-friendly with monkeypatchable paths

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import sqlite3
import shutil
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from decimal import Decimal

# Resolve DB file dynamically to honor engine overrides used in tests
try:
    import src.core.engine as _engine
except Exception:
    _engine = None

try:
    from src.utils.constants import BASE_DIR as _BASE_DIR, DB_FILE as _CONST_DB_FILE
except Exception:
    _BASE_DIR, _CONST_DB_FILE = Path.cwd(), Path.cwd() / 'crypto_master.db'

def _resolve_db_file():
    # Prefer engine's DB_FILE if available (tests monkeypatch this)
    try:
        if _engine and hasattr(_engine, 'DB_FILE'):
            return Path(getattr(_engine, 'DB_FILE'))
    except Exception:
        pass
    return Path(_CONST_DB_FILE)

DB_FILE = _resolve_db_file()
BASE_DIR = _BASE_DIR
from src.utils.config import load_config

logger = logging.getLogger("Crypto_Transaction_Engine")

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
    except (ValueError, TypeError, InvalidOperation) as e:
        logger.warning(f"Invalid decimal value '{value}': {e}")
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
    
    def __init__(self, db_file=None):
        """Initialize database connection and ensure schema is up to date."""
        initialize_folders()
        
        # Determine DB file path dynamically to support test monkeypatching
        if db_file:
            self.db_file = Path(db_file)
        else:
            # Lazy import engine to avoid circular dependency and get patched value
            try:
                import sys
                if 'src.core.engine' in sys.modules:
                    _eng = sys.modules['src.core.engine']
                    if hasattr(_eng, 'DB_FILE'):
                        self.db_file = Path(_eng.DB_FILE)
                    else:
                        self.db_file = Path(DB_FILE)
                else:
                    # Try import if not in modules
                    import src.core.engine as _eng
                    self.db_file = Path(_eng.DB_FILE)
            except Exception:
                self.db_file = Path(DB_FILE)

        self._ensure_integrity()
        self.conn = sqlite3.connect(str(self.db_file), check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _backup_path(self):
        """Get path for safety backup file."""
        return self.db_file.with_suffix('.bak')

    def create_safety_backup(self):
        """
        Create a safety backup of the database before destructive operations.
        Only creates backup if enabled in config.
        """
        if not GLOBAL_CONFIG['general']['create_db_backups']:
            return
        if self.db_file.exists():
            self.conn.commit()
            try:
                shutil.copy(self.db_file, self._backup_path())
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
                shutil.copy(backup_path, self.db_file)
                self.conn = sqlite3.connect(str(self.db_file))
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
        if not self.db_file.exists():
            return
        conn = None
        try:
            conn = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True)
            conn.execute("PRAGMA integrity_check")
            conn.close()
        except Exception as e:
            # If database is locked, do not attempt recovery here (Windows file lock)
            if isinstance(e, sqlite3.OperationalError) and 'locked' in str(e).lower():
                try:
                    if conn:
                        conn.close()
                except Exception:
                    pass
                return
            try:
                if conn:
                    conn.close()
            finally:
                self._recover_db()

    def _get_base_dir(self):
        """Resolve BASE_DIR dynamically to support test monkeypatching."""
        try:
            import sys
            if 'src.core.engine' in sys.modules:
                _eng = sys.modules['src.core.engine']
                if hasattr(_eng, 'BASE_DIR'):
                    return Path(_eng.BASE_DIR)
            # Fallback to local global or constant
            return BASE_DIR
        except Exception:
            return BASE_DIR

    def _recover_db(self):
        """
        Recover from corrupted database by moving it aside.
        Creates a fresh database for new transactions.
        """
        timestamp = datetime.now().strftime("%Y%m%d")
        corrupt_path = self._get_base_dir() / f"CORRUPT_{timestamp}.db"
        shutil.move(str(self.db_file), str(corrupt_path))
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
        try:
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
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower():
                # Defer table initialization; operations will surface lock appropriately
                return
            raise

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
            
            # CONSERVATIVE DEFI LP TREATMENT: Convert LP deposits to Reportable swaps
            if DEFI_LP_CONSERVATIVE:
                action = str(t_copy.get('action', '')).upper()
                coin = str(t_copy.get('coin', ''))
                if action in ['DEPOSIT', 'BUY'] and is_defi_lp_token(coin):
                    # Convert DEPOSIT -> SWAP to treat as Reportable event
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

    # --- Convenience methods used by tests ---
    def add_transaction(self, t):
        """Add a transaction and commit, returning its ID."""
        tx = dict(t)
        if 'id' not in tx or not tx['id']:
            import uuid
            tx['id'] = str(uuid.uuid4())
        # Perform insert on a dedicated connection to allow concurrent threads
        try:
            conn = sqlite3.connect(str(self.db_file), check_same_thread=False)
            cursor = conn.cursor()
            # Normalize numeric fields to strings for TEXT storage
            for field in ['amount', 'price_usd', 'fee']:
                val = tx.get(field, "0")
                tx[field] = str(to_decimal(val)) if val is not None else "0"
            if 'destination' not in tx:
                tx['destination'] = None
            if 'fee_coin' not in tx:
                tx['fee_coin'] = None
            cols = ['id', 'date', 'source', 'destination', 'action', 'coin', 'amount', 'price_usd', 'fee', 'fee_coin']
            values = [tx.get(col) for col in cols]
            cursor.execute(
                """
                INSERT OR IGNORE INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                values
            )
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return tx['id']

    def get_transaction(self, tx_id):
        """Fetch a single transaction as a dict with numeric fields as floats."""
        row = self.cursor.execute("SELECT * FROM trades WHERE id=?", (tx_id,)).fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in self.cursor.description]
        rec = {cols[i]: row[i] for i in range(len(cols))}
        for fld in ['amount', 'price_usd', 'fee']:
            if rec.get(fld) is not None:
                try:
                    rec[fld] = float(rec[fld])
                except Exception:
                    rec[fld] = 0.0
        return rec

    def get_all_transactions(self):
        """Fetch all transactions as list of dicts."""
        conn = sqlite3.connect(str(self.db_file), check_same_thread=False)
        try:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM trades ORDER BY date ASC").fetchall()
            cols = [desc[0] for desc in cursor.description]
            out = []
            for r in rows:
                rec = {cols[i]: r[i] for i in range(len(cols))}
                for fld in ['amount', 'price_usd', 'fee']:
                    if rec.get(fld) is not None:
                        try:
                            rec[fld] = float(rec[fld])
                        except Exception:
                            rec[fld] = 0.0
                out.append(rec)
            return out
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
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
        """Close database connection safely and release file locks."""
        try:
            if hasattr(self, 'conn') and self.conn:
                try:
                    self.conn.commit()
                except Exception:
                    pass
                self.conn.close()
        finally:
            self.conn = None
            self.cursor = None

    # Make DatabaseManager usable as a context manager
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Ensure connections are closed when object is garbage collected
    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
