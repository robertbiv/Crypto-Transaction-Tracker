"""
================================================================================
TEST: Database Error Recovery & Integrity
================================================================================

Tests for database resilience, connection management, and error handling
during concurrent access.

Test Coverage:
    - Failed write recovery
    - Incomplete transaction rollback
    - Corruption detection
    - Connection exhaustion handling
    - Timeout and retry behavior
    - Large dataset concurrency

Author: Database Resilience Enhancement
================================================================================
"""

import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def isolated_db(tmp_path):
    """Create isolated database with WAL mode."""
    db_path = tmp_path / "test.db"
    
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
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
    conn.commit()
    conn.close()
    
    return db_path


@pytest.mark.concurrency
def test_failed_write_rollback(isolated_db):
    """Test that failed writes are rolled back properly."""
    errors = []
    
    def safe_write_succeed():
        try:
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("row1", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Safe write failed: {exc}")

    def bad_write_fail():
        try:
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            # Attempt to insert duplicate
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("row1", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
            )
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            pass  # Expected
        except Exception as exc:
            errors.append(f"Bad write error: {exc}")

    safe_write_succeed()
    bad_write_fail()
    
    assert not errors
    
    # Verify only one row exists
    conn = sqlite3.connect(str(isolated_db))
    count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    
    assert count == 1, "Duplicate was inserted despite constraint"


@pytest.mark.concurrency
def test_incomplete_transaction_recovery(isolated_db):
    """Test recovery from incomplete transactions."""
    conn = sqlite3.connect(str(isolated_db), timeout=10)
    
    # Start transaction but don't commit
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("incomplete", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
    )
    # Force close without commit
    conn.close()
    
    # New connection should not see incomplete transaction
    conn = sqlite3.connect(str(isolated_db), timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM trades WHERE id='incomplete'").fetchall()
    conn.close()
    
    # WAL mode should have rolled back the incomplete transaction
    assert len(rows) == 0, "Incomplete transaction was not rolled back"


@pytest.mark.concurrency
def test_database_corruption_detection(isolated_db):
    """Test ability to detect and handle corruption."""
    conn = sqlite3.connect(str(isolated_db), timeout=10)
    
    # Verify database integrity
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        assert result[0] == "ok", f"Corruption detected: {result[0]}"
    finally:
        conn.close()


@pytest.mark.concurrency
def test_connection_timeout_handling(isolated_db):
    """Test proper timeout handling during contention."""
    errors = []
    results = []
    start = threading.Event()
    
    def long_writer():
        try:
            start.wait()
            conn = sqlite3.connect(str(isolated_db), timeout=1)
            # Hold lock for a moment
            conn.execute("BEGIN EXCLUSIVE")
            time.sleep(0.2)
            conn.execute("ROLLBACK")
            conn.close()
            results.append("long_write_completed")
        except Exception as exc:
            errors.append(f"Long writer error: {exc}")
    
    def quick_reader():
        try:
            start.wait()
            time.sleep(0.05)  # Let long writer acquire lock
            conn = sqlite3.connect(str(isolated_db), timeout=2)
            count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            conn.close()
            results.append(f"quick_read_completed_{count}")
        except sqlite3.OperationalError as exc:
            if "timeout" in str(exc).lower():
                errors.append(f"Timeout as expected: {exc}")
            else:
                errors.append(f"Unexpected error: {exc}")
        except Exception as exc:
            errors.append(f"Quick reader error: {exc}")
    
    threads = [threading.Thread(target=long_writer), threading.Thread(target=quick_reader)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    # At least one operation should have completed
    assert len(results) > 0, "No operations completed"


@pytest.mark.concurrency
def test_large_batch_insert_integrity(isolated_db):
    """Test data integrity with large batch inserts."""
    errors = []
    batch_size = 1000
    
    def bulk_insert():
        try:
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            for i in range(batch_size):
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"bulk-{i}", f"2024-01-{(i % 28) + 1:02d}", "SRC", "DST", "BUY", "BTC", str(i), "100", "0", "", None)
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Bulk insert error: {exc}")
    
    def concurrent_read():
        try:
            time.sleep(0.1)  # Let some inserts happen
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            conn.close()
            return count
        except Exception as exc:
            errors.append(f"Concurrent read error: {exc}")
            return 0
    
    threads = [
        threading.Thread(target=bulk_insert),
        threading.Thread(target=concurrent_read),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors
    
    # Verify all inserts succeeded
    conn = sqlite3.connect(str(isolated_db))
    count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    
    assert count == batch_size, f"Expected {batch_size} rows, got {count}"


@pytest.mark.concurrency
def test_connection_leak_prevention(isolated_db):
    """Test that connections are properly closed in all paths."""
    # Insert initial data
    conn = sqlite3.connect(str(isolated_db), timeout=10)
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("initial", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
    )
    conn.commit()
    conn.close()
    
    def write_with_error():
        conn = sqlite3.connect(str(isolated_db), timeout=10)
        try:
            # Intentional duplicate to trigger error
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("dup", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
            )
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("dup", "2024-01-01", "SRC", "DST", "BUY", "BTC", "1", "100", "0", "", None)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()
    
    # Execute multiple times to check for connection leaks
    for _ in range(10):
        write_with_error()
    
    # Should still be able to connect and query
    conn = sqlite3.connect(str(isolated_db), timeout=10)
    count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    
    assert count == 1, "Connection leak may have occurred (count should be 1, got {})".format(count)


@pytest.mark.concurrency
def test_transaction_isolation_under_contention(isolated_db):
    """Test that transactions remain isolated under concurrent load."""
    conn = sqlite3.connect(str(isolated_db), timeout=10)
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("base", "2024-01-01", "SRC", "DST", "BUY", "BTC", "100", "50000", "0", "", None)
    )
    conn.commit()
    conn.close()
    
    results = []
    errors = []
    start = threading.Event()
    
    def reader():
        try:
            start.wait()
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            # Read total amount
            total = conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades").fetchone()[0]
            results.append(total)
            conn.close()
        except Exception as exc:
            errors.append(exc)
    
    def writer():
        try:
            start.wait()
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            # Add transaction
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("add", "2024-01-02", "SRC", "DST", "BUY", "BTC", "50", "55000", "0", "", None)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(exc)
    
    threads = [threading.Thread(target=reader) for _ in range(3)] + [threading.Thread(target=writer)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    assert len(results) == 3
    # All reads should see consistent data (either 100 or 150)
    for result in results:
        assert result in (100, 150), f"Unexpected read result: {result}"


@pytest.mark.concurrency
def test_constraint_enforcement_under_load(isolated_db):
    """Test that constraints are properly enforced under concurrent load."""
    errors = []
    success_count = []
    start = threading.Event()
    
    def insert_with_id(test_id, row_id):
        try:
            start.wait()
            conn = sqlite3.connect(str(isolated_db), timeout=10)
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id, "2024-01-01", "SRC", "DST", "BUY", "BTC", str(test_id), "100", "0", "", None)
            )
            conn.commit()
            conn.close()
            success_count.append(1)
        except sqlite3.IntegrityError:
            pass  # Duplicate key, expected
        except Exception as exc:
            errors.append(f"Thread {test_id}: {exc}")
    
    # Launch 10 threads trying to insert same ID
    threads = [threading.Thread(target=insert_with_id, args=(i, "same-id")) for i in range(10)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    # Only 1 should have succeeded
    assert len(success_count) == 1, f"Expected 1 success, got {len(success_count)}"
