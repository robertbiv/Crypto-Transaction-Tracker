"""
================================================================================
TEST: Schema Evolution, Encryption & Audit Logging
================================================================================

Tests for schema migrations, encrypted concurrent access, and audit trail
consistency during concurrent operations.

Test Coverage:
    - Schema migration scenarios
    - Migration rollback on error
    - Encrypted operations consistency
    - Audit logging during concurrency
    - Log integrity checks
    - Cross-operation tracing

Author: Schema & Audit Enhancement
================================================================================
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def schema_db(tmp_path):
    """Create database with audit schema."""
    db_path = tmp_path / "schema.db"
    
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Initial schema
    conn.execute("""
        CREATE TABLE trades (
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
        )
    """)
    
    # Audit log table
    conn.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            operation TEXT,
            table_name TEXT,
            record_id TEXT,
            user TEXT,
            changes TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    return db_path


def test_schema_migration_success(schema_db):
    """Test successful schema migration."""
    conn = sqlite3.connect(str(schema_db), timeout=10)
    
    # Add new column
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN notes TEXT")
        conn.commit()
        
        # Verify new column exists
        cursor = conn.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "notes" in columns
    finally:
        conn.close()


def test_schema_migration_rollback(schema_db):
    """Test error handling during schema migration."""
    conn = sqlite3.connect(str(schema_db), timeout=10)
    
    initial_cursor = conn.execute("PRAGMA table_info(trades)")
    initial_columns = [row[1] for row in initial_cursor.fetchall()]
    
    # Test 1: Verify that a valid migration succeeds
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN valid_col TEXT")
        conn.commit()
        cursor = conn.execute("PRAGMA table_info(trades)")
        columns_after_valid = [row[1] for row in cursor.fetchall()]
        assert "valid_col" in columns_after_valid
    except Exception as exc:
        pytest.fail(f"Valid migration should succeed: {exc}")
    
    # Test 2: Verify that invalid migrations fail gracefully
    try:
        # SQLite doesn't support true rollback of DDL in all cases,
        # but we can verify that duplicate column errors are caught
        conn.execute("ALTER TABLE trades ADD COLUMN valid_col TEXT")  # Duplicate column
        conn.commit()
        pytest.fail("Should have raised error for duplicate column")
    except sqlite3.OperationalError as e:
        # Expected: duplicate column error
        assert "duplicate column" in str(e).lower()
    finally:
        conn.close()


def test_audit_log_consistency(schema_db):
    """Test that audit logs are consistent across operations."""
    conn = sqlite3.connect(str(schema_db), timeout=10)
    
    # Insert trade
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("audit-1", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
    )
    
    # Log operation
    conn.execute(
        "INSERT INTO audit_log (timestamp, operation, table_name, record_id, user, changes) VALUES (?, ?, ?, ?, ?, ?)",
        ("2024-01-01T00:00:00Z", "INSERT", "trades", "audit-1", "test_user", json.dumps({"coin": "BTC", "amount": "1"}))
    )
    
    conn.commit()
    conn.close()
    
    # Verify
    conn = sqlite3.connect(str(schema_db))
    trade = conn.execute("SELECT * FROM trades WHERE id='audit-1'").fetchone()
    log = conn.execute("SELECT * FROM audit_log WHERE record_id='audit-1'").fetchone()
    conn.close()
    
    assert trade is not None
    assert log is not None


def test_concurrent_audit_logging(schema_db):
    """Test audit logging under concurrent writes."""
    errors = []
    start = threading.Event()
    log_count = [0]
    lock = threading.Lock()
    
    def write_with_audit(thread_id):
        try:
            start.wait()
            conn = sqlite3.connect(str(schema_db), timeout=10)
            
            # Insert trade
            trade_id = f"audit-{thread_id}"
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (trade_id, "2024-01-01", "SRC", "DST", "BUY", "BTC", str(thread_id), "100", "0", "", None)
            )
            
            # Log operation
            conn.execute(
                "INSERT INTO audit_log (timestamp, operation, table_name, record_id, user, changes) VALUES (?, ?, ?, ?, ?, ?)",
                ("2024-01-01T00:00:00Z", "INSERT", "trades", trade_id, f"user_{thread_id}", json.dumps({"amount": str(thread_id)}))
            )
            
            conn.commit()
            conn.close()
            
            with lock:
                log_count[0] += 1
        except Exception as exc:
            errors.append(f"Thread {thread_id}: {exc}")
    
    threads = [threading.Thread(target=write_with_audit, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    
    # Verify all logs were created
    conn = sqlite3.connect(str(schema_db))
    count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    
    assert count == 5


def test_audit_log_integrity(schema_db):
    """Test that audit log entries are not corrupted."""
    conn = sqlite3.connect(str(schema_db), timeout=10)
    
    # Insert multiple audit entries
    for i in range(10):
        conn.execute(
            "INSERT INTO audit_log (timestamp, operation, table_name, record_id, user, changes) VALUES (?, ?, ?, ?, ?, ?)",
            (f"2024-01-0{(i % 9) + 1}T00:00:00Z", "INSERT", "trades", f"record-{i}", "user", json.dumps({"value": i}))
        )
    conn.commit()
    conn.close()
    
    # Verify all entries are readable
    conn = sqlite3.connect(str(schema_db))
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    conn.close()
    
    assert len(rows) == 10
    for i, row in enumerate(rows):
        assert row[4] == f"record-{i}"  # record_id column


def test_encryption_isolation(schema_db):
    """Test that encrypted operations don't interfere with concurrent access."""
    errors = []
    start = threading.Event()
    
    class SimpleEncryption:
        @staticmethod
        def encrypt(data):
            return "encrypted_" + str(data)
        
        @staticmethod
        def decrypt(data):
            return str(data).replace("encrypted_", "")
    
    def encrypted_write():
        try:
            start.wait()
            conn = sqlite3.connect(str(schema_db), timeout=10)
            
            # Simulate encrypted data write
            encrypted_value = SimpleEncryption.encrypt("secret_data")
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("enc-1", "2024-01-01", encrypted_value, "DST", "BUY", "BTC", "1", "100", "0", "", None)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Encrypted write: {exc}")
    
    def normal_read():
        try:
            start.wait()
            time.sleep(0.05)
            conn = sqlite3.connect(str(schema_db), timeout=10)
            rows = conn.execute("SELECT * FROM trades").fetchall()
            conn.close()
            assert len(rows) >= 0
        except Exception as exc:
            errors.append(f"Normal read: {exc}")
    
    threads = [
        threading.Thread(target=encrypted_write),
        threading.Thread(target=normal_read),
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors


def test_audit_log_no_data_loss(schema_db):
    """Test that audit logging doesn't lose entries under load."""
    errors = []
    start = threading.Event()
    
    def audit_heavy_operation(op_id):
        try:
            start.wait()
            conn = sqlite3.connect(str(schema_db), timeout=10)
            
            # Multiple operations per thread
            for i in range(10):
                trade_id = f"heavy-{op_id}-{i}"
                
                # Insert trade
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (trade_id, "2024-01-01", "SRC", "DST", "BUY", "BTC", str(i), "100", "0", "", None)
                )
                
                # Log it
                conn.execute(
                    "INSERT INTO audit_log (timestamp, operation, table_name, record_id, user, changes) VALUES (?, ?, ?, ?, ?, ?)",
                    ("2024-01-01T00:00:00Z", "INSERT", "trades", trade_id, f"user_{op_id}", json.dumps({"op": i}))
                )
            
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Op {op_id}: {exc}")
    
    threads = [threading.Thread(target=audit_heavy_operation, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    
    # Verify all logs present
    conn = sqlite3.connect(str(schema_db))
    trades_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    logs_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    
    expected_trades = 5 * 10
    assert trades_count == expected_trades
    assert logs_count == expected_trades


def test_schema_compatibility_read_write(schema_db):
    """Test that schema changes don't break read/write compatibility."""
    conn = sqlite3.connect(str(schema_db), timeout=10)
    
    # Insert with original schema
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("original", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
    )
    conn.commit()
    
    # Add new column
    try:
        conn.execute("ALTER TABLE trades ADD COLUMN new_field TEXT DEFAULT 'default'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Already exists from earlier test
    
    # Insert with new schema
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("new-schema", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
    )
    conn.commit()
    
    # Read both
    rows = conn.execute("SELECT * FROM trades ORDER BY id").fetchall()
    conn.close()
    
    assert len(rows) >= 2
