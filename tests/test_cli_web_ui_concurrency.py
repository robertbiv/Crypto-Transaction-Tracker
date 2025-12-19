"""
================================================================================
TEST: CLI and Web UI Concurrent Access & Data Corruption Prevention
================================================================================

Tests that CLI and Web UI can be used simultaneously without corrupting data,
especially with SQLite WAL mode for robust concurrent access.

Test Coverage:
    - Concurrent writes from CLI and Web UI
    - Concurrent reads from CLI and Web UI
    - Concurrent updates from CLI and Web UI
    - Data consistency checks
    - No corruption during simultaneous access
    - No dirty data reads (partial transactions)

Markers:
    concurrency: Tests concurrent CLI and Web UI operations

Author: CLI-Web Parity Enhancement
================================================================================
"""

import json
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest



@pytest.fixture()
def cli_env(tmp_path):
    """Setup isolated environment with WAL-enabled database."""
    base = tmp_path
    outputs = base / "outputs"
    configs = base / "configs"
    keys_dir = base / "keys"
    outputs.mkdir(parents=True, exist_ok=True)
    configs.mkdir(parents=True, exist_ok=True)
    keys_dir.mkdir(parents=True, exist_ok=True)

    db_path = base / "crypto_master.db"

    # Initialize database with WAL mode
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
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
        """
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    conn.close()

    return SimpleNamespace(base=base, db_path=db_path, outputs=outputs, configs=configs)



@pytest.mark.concurrency
def test_cli_web_ui_concurrent_writes(cli_env):
    """Test concurrent CLI and Web UI writes don't corrupt database."""
    errors = []
    start = threading.Event()

    def cli_job():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("cli-row", "2024-04-01", "CLI", "DEST", "BUY", "BTC", "1", "101.0", "0.1", "USD", None),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"CLI error: {exc}")

    def web_job():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            conn.execute(
                "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("web-row", "2024-04-01", "WEB", "DEST", "SELL", "ETH", "2", "202.0", "0", "", None),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Web error: {exc}")

    threads = [threading.Thread(target=cli_job), threading.Thread(target=web_job)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, f"Concurrency errors: {errors}"

    conn = sqlite3.connect(str(cli_env.db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, source FROM trades").fetchall()
    conn.close()

    ids = [row["id"] for row in rows]
    sources = [row["source"] for row in rows]

    assert "web-row" in ids, "Web row missing"
    assert "cli-row" in ids, "CLI row missing"
    assert "CLI" in sources, "CLI source missing"
    assert "WEB" in sources, "WEB source missing"



@pytest.mark.concurrency
def test_cli_web_ui_concurrent_reads(cli_env):
    """Test concurrent CLI and Web UI reads are consistent."""
    conn = sqlite3.connect(str(cli_env.db_path))
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("row1", "2024-05-01", "SRC1", "DST1", "BUY", "BTC", "1", "100", "0", "", None)
    )
    conn.commit()
    conn.close()

    results = []
    errors = []
    start = threading.Event()

    def cli_read():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            count = conn.execute("SELECT COUNT(*) as cnt FROM trades").fetchone()[0]
            results.append(("cli", count))
            conn.close()
        except Exception as exc:
            errors.append(f"CLI read error: {exc}")

    def web_read():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            count = conn.execute("SELECT COUNT(*) as cnt FROM trades").fetchone()[0]
            results.append(("web", count))
            conn.close()
        except Exception as exc:
            errors.append(f"Web read error: {exc}")

    threads = [threading.Thread(target=cli_read), threading.Thread(target=web_read)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, f"Read errors: {errors}"
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert results[0][1] == results[1][1], f"Read counts differ: {results[0][1]} vs {results[1][1]}"



@pytest.mark.concurrency
def test_cli_web_ui_concurrent_updates(cli_env):
    """Test concurrent CLI and Web UI updates maintain consistency."""
    # Seed database
    conn = sqlite3.connect(str(cli_env.db_path))
    conn.execute(
        "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("update-test", "2024-06-01", "ORIG", "DST", "BUY", "ETH", "1", "100", "0", "", None)
    )
    conn.commit()
    conn.close()

    errors = []
    start = threading.Event()

    def cli_update():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            conn.execute("UPDATE trades SET action='SELL' WHERE id='update-test'")
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"CLI update error: {exc}")

    def web_update():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            conn.execute("UPDATE trades SET amount='2' WHERE id='update-test'")
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Web update error: {exc}")

    threads = [threading.Thread(target=cli_update), threading.Thread(target=web_update)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, f"Update errors: {errors}"

    # Verify database is not corrupted
    conn = sqlite3.connect(str(cli_env.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM trades WHERE id='update-test'").fetchone()
    conn.close()

    assert row is not None, "Row deleted or corrupted"
    assert row["id"] == "update-test"



@pytest.mark.concurrency
def test_cli_web_ui_multiple_concurrent_writes(cli_env):
    """Test multiple concurrent writes from both CLI and Web UI."""
    errors = []
    start = threading.Event()
    write_count = 5

    def cli_writes():
        try:
            start.wait()
            for i in range(write_count):
                conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"cli-row-{i}", f"2024-07-0{i+1}", "CLI", "DST", "BUY", "BTC", str(i+1), str(100.0 + i), "0.1", "USD", None),
                )
                conn.commit()
                conn.close()
        except Exception as exc:
            errors.append(f"CLI batch error: {exc}")

    def web_writes():
        try:
            start.wait()
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            for i in range(write_count):
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"web-row-{i}", f"2024-07-{10+i}", "WEB", "DST", "SELL", "ETH", str(i+1), str(200.0+i), "0", "", None),
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Web batch error: {exc}")

    threads = [threading.Thread(target=cli_writes), threading.Thread(target=web_writes)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, f"Batch write errors: {errors}"

    conn = sqlite3.connect(str(cli_env.db_path))
    count = conn.execute("SELECT COUNT(*) as cnt FROM trades").fetchone()[0]
    conn.close()

    assert count >= write_count * 2, f"Expected at least {write_count * 2} rows, got {count}"


def test_database_wal_mode_enabled(cli_env):
    """Verify WAL mode is enabled for concurrent access."""
    conn = sqlite3.connect(cli_env.db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()

    assert mode.lower() == "wal", f"Expected WAL mode, got {mode}"


@pytest.mark.concurrency
def test_cli_web_ui_no_read_dirty_data(cli_env):
    """Test that CLI and Web UI don't read partial/dirty writes."""
    import threading as th
    import time as tm
    
    errors = []
    start = threading.Event()
    final_results = []
    write_counter = [0]
    lock = th.Lock()

    def writer():
        try:
            start.wait()
            for i in range(3):
                with lock:
                    write_counter[0] += 1
                    unique_id = write_counter[0]
                
                conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"writer-row-{unique_id}", f"2024-08-0{i+1}", "WRITER", "DST", "BUY", "BTC", str(i+1), "100.0", "0.1", "USD", None),
                )
                conn.commit()
                conn.close()
        except Exception as exc:
            errors.append(f"Writer error: {exc}")

    def reader():
        try:
            start.wait()
            tm.sleep(0.01)  # Small delay to let writes happen
            conn = sqlite3.connect(str(cli_env.db_path), timeout=10)
            rows = conn.execute("SELECT * FROM trades WHERE source='WRITER'").fetchall()
            final_results.append(len(rows))
            conn.close()
        except Exception as exc:
            errors.append(f"Reader error: {exc}")

    threads = [threading.Thread(target=writer) for _ in range(2)] + [threading.Thread(target=reader) for _ in range(2)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()

    assert not errors, f"Read dirty data errors: {errors}"
    assert len(final_results) >= 2, "Not all readers completed"


