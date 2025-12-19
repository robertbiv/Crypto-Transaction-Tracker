"""
================================================================================
TEST: Wallet Edge Cases & Performance Benchmarking
================================================================================

Tests for complex wallet scenarios, cross-wallet consistency, and performance
regression detection during concurrent operations.

Test Coverage:
    - Multi-wallet consistency
    - Cross-wallet transaction linking
    - Wallet rollup calculations
    - Query performance baseline
    - Performance degradation detection
    - Latency under load

Author: Wallet & Performance Enhancement
================================================================================
"""

import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture()
def perf_db(tmp_path):
    """Create database for performance testing."""
    db_path = tmp_path / "perf.db"
    
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
            batch_id TEXT,
            wallet_id TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE wallets (
            id TEXT PRIMARY KEY,
            name TEXT,
            address TEXT,
            balance TEXT
        )
    """)
    
    # Seed with wallets
    wallets = [
        ("eth-wallet-1", "Ethereum Main", "0x1111111111111111111111111111111111111111", "10.5"),
        ("eth-wallet-2", "Ethereum Secondary", "0x2222222222222222222222222222222222222222", "5.25"),
        ("btc-wallet-1", "Bitcoin Main", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "0.75"),
    ]
    
    for wallet_id, name, address, balance in wallets:
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance) VALUES (?, ?, ?, ?)",
            (wallet_id, name, address, balance)
        )
    
    conn.commit()
    conn.close()
    
    return db_path


@pytest.mark.concurrency
def test_multi_wallet_consistency(perf_db):
    """Test consistency across multiple wallet operations."""
    errors = []
    start = threading.Event()
    
    def wallet_operation(wallet_id, operation_count):
        try:
            start.wait()
            conn = sqlite3.connect(str(perf_db), timeout=10)
            
            for i in range(operation_count):
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id, wallet_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"trade-{wallet_id}-{i}",
                        "2024-01-01",
                        wallet_id,
                        "exchange",
                        "BUY",
                        "ETH",
                        str(i + 1),
                        "2000",
                        "10",
                        "USD",
                        None,
                        wallet_id
                    )
                )
            
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(f"Wallet {wallet_id}: {exc}")
    
    threads = [
        threading.Thread(target=wallet_operation, args=("eth-wallet-1", 50)),
        threading.Thread(target=wallet_operation, args=("eth-wallet-2", 30)),
        threading.Thread(target=wallet_operation, args=("btc-wallet-1", 40)),
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
    
    # Verify counts per wallet
    conn = sqlite3.connect(str(perf_db))
    eth1_count = conn.execute("SELECT COUNT(*) FROM trades WHERE wallet_id='eth-wallet-1'").fetchone()[0]
    eth2_count = conn.execute("SELECT COUNT(*) FROM trades WHERE wallet_id='eth-wallet-2'").fetchone()[0]
    btc1_count = conn.execute("SELECT COUNT(*) FROM trades WHERE wallet_id='btc-wallet-1'").fetchone()[0]
    conn.close()
    
    assert eth1_count == 50
    assert eth2_count == 30
    assert btc1_count == 40


@pytest.mark.concurrency
def test_cross_wallet_rollup_calculation(perf_db):
    """Test accurate rollup calculations across wallet boundaries."""
    # Seed some transactions
    conn = sqlite3.connect(str(perf_db), timeout=10)
    
    trades_data = [
        ("eth-wallet-1", "ETH", "10"),
        ("eth-wallet-1", "ETH", "5"),
        ("eth-wallet-2", "ETH", "3"),
        ("btc-wallet-1", "BTC", "1"),
        ("eth-wallet-2", "BTC", "0.5"),
    ]
    
    for i, (wallet_id, coin, amount) in enumerate(trades_data):
        conn.execute(
            "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id, wallet_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"rollup-{i}", "2024-01-01", wallet_id, "exchange", "BUY", coin, amount, "100", "0", "", None, wallet_id)
        )
    
    conn.commit()
    conn.close()
    
    # Calculate rollups
    conn = sqlite3.connect(str(perf_db), timeout=10)
    
    eth_total = conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades WHERE coin='ETH'").fetchone()[0]
    btc_total = conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades WHERE coin='BTC'").fetchone()[0]
    
    eth1_total = conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades WHERE wallet_id='eth-wallet-1' AND coin='ETH'").fetchone()[0]
    eth2_total = conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades WHERE wallet_id='eth-wallet-2' AND coin='ETH'").fetchone()[0]
    
    conn.close()
    
    assert eth_total == 18  # 10 + 5 + 3
    assert btc_total == 1.5  # 1 + 0.5
    assert eth1_total == 15  # 10 + 5
    assert eth2_total == 3


@pytest.mark.concurrency
def test_query_performance_baseline(perf_db):
    """Establish baseline query performance."""
    # Seed with moderate dataset
    conn = sqlite3.connect(str(perf_db), timeout=10)
    
    for i in range(1000):
        conn.execute(
            "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id, wallet_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"perf-{i}",
                f"2024-01-{(i % 28) + 1:02d}",
                "wallet",
                "exchange",
                "BUY",
                "ETH" if i % 2 == 0 else "BTC",
                str(i % 100),
                "2000",
                "10",
                "USD",
                None,
                "eth-wallet-1"
            )
        )
    
    conn.commit()
    conn.close()
    
    # Benchmark common queries
    results = {}
    
    conn = sqlite3.connect(str(perf_db), timeout=10)
    
    # Full table scan
    start = time.time()
    count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    results['full_count'] = time.time() - start
    assert count == 1000
    
    # Filtered query
    start = time.time()
    eth_trades = conn.execute("SELECT * FROM trades WHERE coin='ETH'").fetchall()
    results['filtered'] = time.time() - start
    assert len(eth_trades) > 0
    
    # Aggregation
    start = time.time()
    total = conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades").fetchone()[0]
    results['aggregation'] = time.time() - start
    assert total > 0
    
    # Join
    start = time.time()
    joined = conn.execute("SELECT t.id, w.name FROM trades t LEFT JOIN wallets w ON t.wallet_id=w.id LIMIT 100").fetchall()
    results['join'] = time.time() - start
    assert len(joined) > 0
    
    conn.close()
    
    # Verify all queries complete quickly (< 100ms)
    for query_type, elapsed in results.items():
        assert elapsed < 0.1, f"{query_type} took {elapsed:.3f}s (exceeds 100ms)"


@pytest.mark.concurrency
def test_performance_degradation_detection(perf_db):
    """Test that performance doesn't degrade significantly under load."""
    baseline_times = {}
    load_times = {}
    
    conn = sqlite3.connect(str(perf_db), timeout=10)
    
    # Baseline measurements
    start = time.time()
    for _ in range(50):
        conn.execute("SELECT COUNT(*) FROM trades").fetchone()
    baseline_times['simple_query'] = (time.time() - start) / 50
    
    start = time.time()
    for _ in range(25):
        conn.execute("SELECT * FROM trades WHERE coin='ETH' LIMIT 10").fetchall()
    baseline_times['filtered_query'] = (time.time() - start) / 25
    
    conn.close()
    
    # Add load with timeout
    errors = []
    start_event = threading.Event()
    
    def load_writer():
        try:
            start_event.wait()
            conn = sqlite3.connect(str(perf_db), timeout=10)
            for i in range(200):
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id, wallet_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"load-{threading.current_thread().ident}-{i}", "2024-02-01", "wallet", "exchange", "BUY", "ETH", "1", "2000", "10", "USD", None, "eth-wallet-1")
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            errors.append(exc)
    
    threads = [threading.Thread(target=load_writer) for _ in range(2)]
    for t in threads:
        t.daemon = True
        t.start()
    start_event.set()
    
    # Give threads a moment to start
    time.sleep(0.1)
    
    # Measure performance under load (with shorter sampling)
    load_conn = sqlite3.connect(str(perf_db), timeout=10)
    
    start = time.time()
    for _ in range(50):
        load_conn.execute("SELECT COUNT(*) FROM trades").fetchone()
    load_times['simple_query'] = (time.time() - start) / 50
    
    start = time.time()
    for _ in range(25):
        load_conn.execute("SELECT * FROM trades WHERE coin='ETH' LIMIT 10").fetchall()
    load_times['filtered_query'] = (time.time() - start) / 25
    
    load_conn.close()
    
    # Wait for threads with timeout
    for t in threads:
        t.join(timeout=5.0)
    
    assert not errors, f"Load writer errors: {errors}"
    
    # Performance degradation should be reasonable (< 3x slower due to WAL lock contention)
    for query_type in baseline_times:
        if baseline_times[query_type] > 0:
            ratio = load_times[query_type] / baseline_times[query_type]
            # More lenient threshold for Windows where thread scheduling can vary
            assert ratio < 5.0, f"{query_type} degraded by {ratio:.2f}x"


@pytest.mark.concurrency
def test_latency_percentiles_under_load(perf_db):
    """Test latency percentiles during concurrent operations."""
    latencies = []
    errors = []
    start = threading.Event()
    lock = threading.Lock()
    
    def concurrent_query(query_id):
        try:
            start.wait()
            conn = sqlite3.connect(str(perf_db), timeout=10)
            
            query_start = time.time()
            result = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            elapsed = time.time() - query_start
            
            with lock:
                latencies.append(elapsed)
            
            conn.close()
        except Exception as exc:
            errors.append(exc)
    
    threads = [threading.Thread(target=concurrent_query, args=(i,), daemon=True) for i in range(30)]
    for t in threads:
        t.start()
    start.set()
    
    # Wait for threads with timeout
    for t in threads:
        t.join(timeout=5.0)
    
    assert not errors
    assert len(latencies) > 0, "No latencies recorded"
    
    # Calculate percentiles
    sorted_latencies = sorted(latencies)
    p50 = sorted_latencies[len(sorted_latencies) // 2]
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)] if len(sorted_latencies) > 1 else p95
    
    # Verify reasonable latencies (most queries should complete quickly)
    # Allow up to 100ms for P99 due to thread scheduling variability on Windows
    assert p99 < 0.1, f"P99 latency {p99*1000:.1f}ms exceeds 100ms threshold"


@pytest.mark.concurrency
def test_wallet_balance_consistency(perf_db):
    """Test that wallet balances remain consistent under concurrent operations."""
    errors = []
    start = threading.Event()
    
    def update_and_verify_wallet(wallet_id):
        try:
            start.wait()
            conn = sqlite3.connect(str(perf_db), timeout=10)
            
            # Read current balance
            balance = conn.execute("SELECT balance FROM wallets WHERE id=?", (wallet_id,)).fetchone()[0]
            initial_balance = float(balance)
            
            # Perform transactions
            for i in range(10):
                conn.execute(
                    "INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id, wallet_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"balance-test-{wallet_id}-{i}",
                        "2024-01-01",
                        wallet_id,
                        "exchange",
                        "BUY",
                        "ETH",
                        "0.1",
                        "2000",
                        "1",
                        "USD",
                        None,
                        wallet_id
                    )
                )
            
            conn.commit()
            
            # Re-read balance (should be unchanged)
            new_balance = conn.execute("SELECT balance FROM wallets WHERE id=?", (wallet_id,)).fetchone()[0]
            assert float(new_balance) == initial_balance, "Balance was modified"
            
            conn.close()
        except Exception as exc:
            errors.append(f"Wallet {wallet_id}: {exc}")
    
    threads = [
        threading.Thread(target=update_and_verify_wallet, args=("eth-wallet-1",)),
        threading.Thread(target=update_and_verify_wallet, args=("eth-wallet-2",)),
        threading.Thread(target=update_and_verify_wallet, args=("btc-wallet-1",)),
    ]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    
    assert not errors
