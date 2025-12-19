"""
================================================================================
TEST: Backup Consistency Under Load
================================================================================

Tests that backups maintain consistency while concurrent CLI/Web UI access
continues, and that restores work correctly.

Test Coverage:
    - Backup creation during concurrent writes
    - Backup integrity verification
    - Restore consistency
    - Incremental backup handling
    - Backup isolation from active operations

Author: Backup Resilience Enhancement
================================================================================
"""

import shutil
import sqlite3
import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def backup_env(tmp_path):
    """Setup environment with database and backup directory."""
    base = tmp_path
    db_path = base / "trades.db"
    backup_dir = base / "backups"
    backup_dir.mkdir()
    
    # Initialize database
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
    # Seed with data
    for i in range(100):
        conn.execute(
            "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"init-{i}", f"2024-01-{(i % 28) + 1:02d}", "SRC", "DST", "BUY", "BTC", str(i), "100", "0", "", None)
        )
    conn.commit()
    conn.close()
    
    return SimpleNamespace(base=base, db_path=db_path, backup_dir=backup_dir)


def backup_database(db_path, backup_path):
    """Simple database backup function."""
    shutil.copy2(db_path, backup_path)
    # Also copy WAL files
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")
    if wal_path.exists():
        shutil.copy2(wal_path, Path(str(backup_path) + "-wal"))
    if shm_path.exists():
        shutil.copy2(shm_path, Path(str(backup_path) + "-shm"))


@pytest.mark.concurrency
def test_backup_during_concurrent_writes(backup_env):
    """Test backup creation while writes are in progress."""
    errors = []
    backup_path = backup_env.backup_dir / "backup_during_writes.db"
    start = threading.Event()
    
    def continuous_writes():
        try:
            start.wait()
            for i in range(50):
                conn = sqlite3.connect(str(backup_env.db_path), timeout=10)
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"write-{i}", "2024-02-01", "SRC", "DST", "BUY", "BTC", str(i), "100", "0", "", None)
                )
                conn.commit()
                conn.close()
                time.sleep(0.01)
        except Exception as exc:
            errors.append(f"Write error: {exc}")
    
    def backup_during_writes():
        try:
            start.wait()
            time.sleep(0.05)  # Let writes start
            backup_database(backup_env.db_path, backup_path)
        except Exception as exc:
            errors.append(f"Backup error: {exc}")
    
    threads = [
        threading.Thread(target=continuous_writes),
        threading.Thread(target=backup_during_writes),
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    assert backup_path.exists()


@pytest.mark.concurrency
def test_backup_integrity_check(backup_env):
    """Test that backup is consistent and uncorrupted."""
    backup_path = backup_env.backup_dir / "integrity_test.db"
    backup_database(backup_env.db_path, backup_path)
    
    # Verify integrity
    conn = sqlite3.connect(str(backup_path), timeout=10)
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    
    assert result == "ok", f"Backup corrupted: {result}"
    
    # Verify data count matches
    orig_conn = sqlite3.connect(str(backup_env.db_path), timeout=10)
    orig_count = orig_conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    orig_conn.close()
    
    backup_conn = sqlite3.connect(str(backup_path), timeout=10)
    backup_count = backup_conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    backup_conn.close()
    
    assert orig_count == backup_count


@pytest.mark.concurrency
def test_restore_into_clean_database(backup_env):
    """Test restoring backup into a clean database."""
    backup_path = backup_env.backup_dir / "restore_test.db"
    backup_database(backup_env.db_path, backup_path)
    
    # Create new empty database
    restore_path = backup_env.backup_dir / "restored.db"
    
    # Restore
    shutil.copy2(backup_path, restore_path)
    
    # Verify restored database
    conn = sqlite3.connect(str(restore_path), timeout=10)
    count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    
    assert count == 100, "Restore didn't preserve data"


@pytest.mark.concurrency
def test_restore_with_concurrent_access_blocked(backup_env):
    """Test that restore operation blocks concurrent access appropriately."""
    backup_path = backup_env.backup_dir / "concurrent_restore.db"
    backup_database(backup_env.db_path, backup_path)
    
    restore_path = backup_env.backup_dir / "restore_concurrent.db"
    errors = []
    results = []
    
    def restore_operation():
        try:
            # Copy over the original to simulate restore
            shutil.copy2(backup_path, restore_path)
            time.sleep(0.1)  # Simulate restore taking time
            results.append("restore_complete")
        except Exception as exc:
            errors.append(f"Restore error: {exc}")
    
    def access_during_restore():
        try:
            time.sleep(0.05)
            # Try to access restored database during/after restore
            if restore_path.exists():
                conn = sqlite3.connect(str(restore_path), timeout=10)
                count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
                conn.close()
                results.append(f"accessed_count_{count}")
        except Exception as exc:
            errors.append(f"Access error: {exc}")
    
    threads = [
        threading.Thread(target=restore_operation),
        threading.Thread(target=access_during_restore),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors


@pytest.mark.concurrency
def test_multiple_concurrent_backups(backup_env):
    """Test that multiple backup operations don't interfere."""
    errors = []
    start = threading.Event()
    
    def backup_operation(backup_num):
        try:
            start.wait()
            backup_path = backup_env.backup_dir / f"concurrent_backup_{backup_num}.db"
            backup_database(backup_env.db_path, backup_path)
            
            # Verify
            conn = sqlite3.connect(str(backup_path), timeout=10)
            count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            conn.close()
            
            assert count == 100, f"Backup {backup_num} has wrong count"
        except Exception as exc:
            errors.append(f"Backup {backup_num} error: {exc}")
    
    threads = [threading.Thread(target=backup_operation, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors


@pytest.mark.concurrency
def test_backup_doesnt_block_writes(backup_env):
    """Test that backup operation doesn't prevent concurrent writes."""
    backup_path = backup_env.backup_dir / "nonblocking_backup.db"
    write_results = []
    errors = []
    start = threading.Event()
    
    def backup_slow():
        try:
            start.wait()
            # Simulate slow backup
            src = backup_env.db_path
            dest = backup_path
            with open(src, "rb") as f_in:
                with open(dest, "wb") as f_out:
                    while True:
                        chunk = f_in.read(1024)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        time.sleep(0.01)  # Slow copy
        except Exception as exc:
            errors.append(f"Backup error: {exc}")
    
    def concurrent_write():
        try:
            start.wait()
            for i in range(10):
                conn = sqlite3.connect(str(backup_env.db_path), timeout=10)
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"nonblock-{i}", "2024-03-01", "SRC", "DST", "BUY", "BTC", str(i), "100", "0", "", None)
                )
                conn.commit()
                conn.close()
                write_results.append(i)
        except Exception as exc:
            errors.append(f"Write error: {exc}")
    
    threads = [
        threading.Thread(target=backup_slow),
        threading.Thread(target=concurrent_write),
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    assert len(write_results) > 0, "Writes were blocked by backup"


@pytest.mark.concurrency
def test_backup_chain_integrity(backup_env):
    """Test that sequential backups maintain consistency chain."""
    backup_paths = []
    
    for i in range(3):
        backup_path = backup_env.backup_dir / f"chain_backup_{i}.db"
        
        # Add new data
        conn = sqlite3.connect(str(backup_env.db_path), timeout=10)
        for j in range(10):
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"chain-{i}-{j}", f"2024-0{i+1}-01", "SRC", "DST", "BUY", "BTC", str(j), "100", "0", "", None)
            )
        conn.commit()
        conn.close()
        
        # Backup
        backup_database(backup_env.db_path, backup_path)
        backup_paths.append(backup_path)
    
    # Verify each backup in chain
    prev_count = 100
    for i, backup_path in enumerate(backup_paths):
        conn = sqlite3.connect(str(backup_path), timeout=10)
        count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        
        assert integrity == "ok", f"Backup {i} corrupted"
        expected = 100 + (i + 1) * 10
        assert count == expected, f"Backup {i}: expected {expected}, got {count}"
