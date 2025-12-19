"""
Database schema and Decimal handling guidelines.
Ensures numeric precision is preserved through DB layer.

KEY PRINCIPLES:
1. Store numeric amounts as TEXT or NUMERIC (not REAL/FLOAT)
2. Retrieve and convert to Decimal immediately
3. All comparisons/calculations in Decimal space
4. Store as TEXT for maximum portability if NUMERIC unavailable
"""

import sqlite3
from decimal import Decimal
from typing import Optional, List, Dict, Any
from src.decimal_utils import to_decimal


# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

CREATE_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    action TEXT NOT NULL,
    coin TEXT NOT NULL,
    amount TEXT NOT NULL,  -- Store as TEXT to preserve precision
    price_usd TEXT NOT NULL,  -- Store as TEXT to preserve precision
    source TEXT DEFAULT 'manual',
    description TEXT DEFAULT '',
    fraud_score TEXT,  -- Decimal stored as TEXT
    ai_description TEXT DEFAULT '',
    anomaly_flag INTEGER DEFAULT 0,
    cost_basis TEXT,  -- Cost basis in USD (TEXT for precision)
    proceeds TEXT,  -- Sale proceeds in USD (TEXT for precision)
    capital_gain TEXT,  -- Capital gain/loss (TEXT for precision)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PATTERNS_TABLE = """
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    action TEXT NOT NULL,
    avg_amount TEXT,  -- Average amount (TEXT for precision)
    avg_price TEXT,  -- Average price (TEXT for precision)
    std_dev_amount TEXT,  -- Standard deviation (TEXT for precision)
    std_dev_price TEXT,  -- Standard deviation (TEXT for precision)
    min_transactions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_WASH_SALES_TABLE = """
CREATE TABLE IF NOT EXISTS wash_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    buy_tx_id INTEGER NOT NULL,
    sell_tx_id INTEGER NOT NULL,
    buy_price TEXT NOT NULL,  -- Store as TEXT
    sell_price TEXT NOT NULL,  -- Store as TEXT
    days_apart INTEGER,
    adjustment_needed INTEGER DEFAULT 1,
    adjustment_amount TEXT,  -- Adjustment in USD (TEXT for precision)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# ============================================================================
# HELPER FUNCTIONS FOR DECIMAL DB OPERATIONS
# ============================================================================

def insert_trade_with_decimals(
    conn: sqlite3.Connection,
    date: str,
    action: str,
    coin: str,
    amount: Decimal,
    price_usd: Decimal,
    source: str = 'manual',
    description: str = '',
    fraud_score: Optional[Decimal] = None,
    cost_basis: Optional[Decimal] = None,
    proceeds: Optional[Decimal] = None,
    capital_gain: Optional[Decimal] = None,
) -> int:
    """
    Insert a trade with Decimal amounts preserved as TEXT in DB.
    
    Returns the inserted row id.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades 
        (date, action, coin, amount, price_usd, source, description, 
         fraud_score, cost_basis, proceeds, capital_gain)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date, action, coin,
        str(amount), str(price_usd),  # Convert Decimals to TEXT
        source, description,
        str(fraud_score) if fraud_score else None,
        str(cost_basis) if cost_basis else None,
        str(proceeds) if proceeds else None,
        str(capital_gain) if capital_gain else None,
    ))
    conn.commit()
    return cursor.lastrowid


def fetch_trade_with_decimals(
    conn: sqlite3.Connection,
    trade_id: int
) -> Optional[Dict[str, Any]]:
    """
    Fetch a trade and convert TEXT amounts back to Decimals.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    tx = dict(row)
    # Convert TEXT fields back to Decimal
    decimal_fields = ['amount', 'price_usd', 'fraud_score', 'cost_basis', 'proceeds', 'capital_gain']
    for field in decimal_fields:
        if field in tx and tx[field]:
            tx[field] = to_decimal(tx[field])
    
    return tx


def fetch_all_trades_with_decimals(
    conn: sqlite3.Connection,
    coin: Optional[str] = None,
    action: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch multiple trades and convert TEXT amounts to Decimals.
    """
    cursor = conn.cursor()
    
    query = "SELECT * FROM trades WHERE 1=1"
    params = []
    
    if coin:
        query += " AND coin = ?"
        params.append(coin)
    
    if action:
        query += " AND action = ?"
        params.append(action)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = []
    for row in rows:
        tx = dict(row)
        decimal_fields = ['amount', 'price_usd', 'fraud_score', 'cost_basis', 'proceeds', 'capital_gain']
        for field in decimal_fields:
            if field in tx and tx[field]:
                tx[field] = to_decimal(tx[field])
        result.append(tx)
    
    return result


# ============================================================================
# MIGRATION NOTES
# ============================================================================

"""
MIGRATION CHECKLIST FOR EXISTING DATABASES:

1. Backup existing database before migration:
   $ cp crypto_master.db crypto_master.db.backup

2. For existing REAL columns, migrate to TEXT:
   ALTER TABLE trades RENAME TO trades_old;
   CREATE TABLE trades (...new schema with TEXT...);
   INSERT INTO trades SELECT 
       id, date, action, coin, 
       CAST(amount AS TEXT),      -- Convert REAL to TEXT
       CAST(price_usd AS TEXT),   -- Convert REAL to TEXT
       source, description, fraud_score, ai_description, anomaly_flag,
       CAST(cost_basis AS TEXT),
       CAST(proceeds AS TEXT),
       CAST(capital_gain AS TEXT),
       created_at, updated_at
   FROM trades_old;
   DROP TABLE trades_old;

3. Verify precision after migration:
   SELECT amount, price_usd FROM trades LIMIT 5;
   -- Should show full decimal places

4. Test with Python layer:
   from src.precision_audit_logger import *
   trades = fetch_all_trades_with_decimals(conn)
   for tx in trades:
       assert isinstance(tx['amount'], Decimal)
       print(tx['amount'])  # Full precision preserved
"""
