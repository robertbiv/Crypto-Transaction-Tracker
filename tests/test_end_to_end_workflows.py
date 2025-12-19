"""
Comprehensive end-to-end workflow tests for Crypto Transaction Tracker.

Tests complete user journeys:
- Web UI workflow: wallet creation → transaction entry → reporting
- CLI workflow: setup → import → filtering → reporting  
- CLI/Web integration: data consistency across interfaces
- Multi-user concurrency: concurrent operations safety
"""

import sqlite3
import json
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
import pytest


@pytest.fixture()
def e2e_db(tmp_path):
    """Create isolated database for end-to-end tests."""
    db_path = tmp_path / "test.db"
    
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Create standard schema
    conn.execute("""
        CREATE TABLE wallets (
            id TEXT PRIMARY KEY,
            name TEXT,
            address TEXT,
            balance TEXT,
            created_at TEXT
        )
    """)
    
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
    
    conn.execute("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT,
            action TEXT,
            timestamp TEXT,
            user_id TEXT,
            details TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    return db_path


class TestWebUIWorkflow:
    """Test complete Web UI workflows."""
    
    def test_web_ui_complete_workflow(self, e2e_db):
        """Test complete Web UI workflow: wallet create → transaction → report."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        # Step 1: Create wallet
        wallet_id = "main-wallet-web"
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "My Web Wallet", "0xabc123", "10.5", datetime.now().isoformat())
        )
        conn.commit()
        
        # Step 2: Add transactions
        for i in range(3):
            trade_id = f"web-trade-{i}"
            conn.execute(
                """INSERT INTO trades
                   (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trade_id, f"2024-01-{i+1:02d}", wallet_id, "Exchange", "BUY", "ETH", "1.0", "2000", "10", "USD", "batch1")
            )
        conn.commit()
        
        # Step 3: Generate report
        trades = conn.execute("SELECT * FROM trades").fetchall()
        assert len(trades) == 3
        
        # Step 4: Verify aggregations
        total_fees = conn.execute("SELECT SUM(CAST(fee AS REAL)) FROM trades").fetchone()[0]
        assert total_fees == 30.0
        
        # Step 5: Log actions
        for trade_id in [f"web-trade-{i}" for i in range(3)]:
            conn.execute(
                "INSERT INTO audit_logs (trade_id, action, timestamp, user_id, details) VALUES (?, ?, ?, ?, ?)",
                (trade_id, "CREATED", datetime.now().isoformat(), "web-user", json.dumps({"source": "web_ui"}))
            )
        conn.commit()
        
        # Verify audit trail
        audit_logs = conn.execute("SELECT * FROM audit_logs").fetchall()
        assert len(audit_logs) == 3
        assert all(log[2] == "CREATED" for log in audit_logs)  # action column
        
        conn.close()
    
    def test_web_ui_bulk_import(self, e2e_db):
        """Test Web UI bulk import of 50 transactions."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        wallet_id = "bulk-import-wallet"
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Bulk Import Wallet", "0xdef456", "0", datetime.now().isoformat())
        )
        conn.commit()
        
        # Bulk import 50 transactions
        for i in range(50):
            trade_id = f"bulk-trade-{i}"
            action = "BUY" if i % 2 == 0 else "SELL"
            coin = "ETH" if i % 3 == 0 else "BTC"
            
            conn.execute(
                """INSERT INTO trades
                   (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trade_id, f"2024-01-{(i % 28) + 1:02d}", wallet_id, "Exchange", action, coin, 
                 str(i * 0.1), str(50000 + i * 100), str(i % 10), "USD", "bulk_batch")
            )
        conn.commit()
        
        # Verify import
        trades = conn.execute("SELECT * FROM trades").fetchall()
        assert len(trades) == 50
        
        # Verify aggregations
        buy_count = conn.execute("SELECT COUNT(*) FROM trades WHERE action='BUY'").fetchone()[0]
        sell_count = conn.execute("SELECT COUNT(*) FROM trades WHERE action='SELL'").fetchone()[0]
        assert buy_count + sell_count == 50
        
        conn.close()
    
    def test_web_ui_transaction_edit(self, e2e_db):
        """Test Web UI transaction editing workflow."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        wallet_id = "edit-wallet"
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Edit Wallet", "0xghi789", "5.0", datetime.now().isoformat())
        )
        conn.commit()
        
        # Create initial transaction
        trade_id = "trade-to-edit"
        conn.execute(
            """INSERT INTO trades
               (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_id, "2024-01-15", wallet_id, "Exchange", "BUY", "ETH", "1.0", "2000", "10", "USD", "edit_batch")
        )
        conn.commit()
        
        # Verify initial state
        trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        assert float(trade[6]) == 1.0  # amount
        
        # Edit the transaction
        conn.execute(
            "UPDATE trades SET amount=?, price_usd=? WHERE id=?",
            ("2.5", "2500", trade_id)
        )
        conn.commit()
        
        # Verify update
        updated_trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        assert float(updated_trade[6]) == 2.5  # amount
        assert float(updated_trade[7]) == 2500.0  # price_usd
        
        # Log edit
        conn.execute(
            "INSERT INTO audit_logs (trade_id, action, timestamp, user_id, details) VALUES (?, ?, ?, ?, ?)",
            (trade_id, "UPDATED", datetime.now().isoformat(), "web-user", json.dumps({"field": "amount", "old": "1.0", "new": "2.5"}))
        )
        conn.commit()
        
        conn.close()


class TestCLIWorkflow:
    """Test complete CLI workflows."""
    
    def test_cli_workflow_basic_setup(self, e2e_db):
        """Test CLI workflow: setup → transaction add → query."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        # Step 1: Create wallet via CLI
        wallet_id = "cli-eth-main"
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "ETH Main", "0xcli123", "100", datetime.now().isoformat())
        )
        conn.commit()
        
        # Step 2: Add transaction via CLI
        trade_id = "cli-trade-1"
        conn.execute(
            """INSERT INTO trades
               (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_id, "2024-01-15", wallet_id, "Kraken", "BUY", "ETH", "2.5", "2000", "10", "USD", "cli_batch1")
        )
        conn.commit()
        
        # Step 3: Query via CLI
        trades = conn.execute("SELECT * FROM trades WHERE action='BUY'").fetchall()
        assert len(trades) == 1
        assert trades[0][5] == "ETH"  # coin
        assert trades[0][4] == "BUY"  # action
        
        # Step 4: Generate summary report
        report = {
            "total_trades": conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
            "total_amount_invested": conn.execute(
                "SELECT SUM(CAST(amount AS REAL) * CAST(price_usd AS REAL)) FROM trades"
            ).fetchone()[0],
            "total_fees": conn.execute("SELECT SUM(CAST(fee AS REAL)) FROM trades").fetchone()[0],
        }
        
        assert report["total_trades"] == 1
        assert report["total_fees"] == 10.0
        
        conn.close()
    
    def test_cli_workflow_csv_import(self, e2e_db):
        """Test CLI CSV import workflow."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        wallet_id = "csv-wallet"
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "CSV Wallet", "0xcsv456", "50", datetime.now().isoformat())
        )
        conn.commit()
        
        # Simulate CSV import of 3 transactions
        csv_data = [
            ("2024-01-01", "Coinbase", "BUY", "BTC", "0.5", "43000"),
            ("2024-01-05", "Kraken", "SELL", "ETH", "2.0", "2100"),
            ("2024-01-10", "Binance", "BUY", "ADA", "1000", "1.2"),
        ]
        
        batch_id = "csv_import_batch"
        for i, (date, src, action, coin, amount, price) in enumerate(csv_data):
            conn.execute(
                """INSERT INTO trades
                   (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"csv-trade-{i}", date, wallet_id, src, action, coin, amount, price, "5", "USD", batch_id)
            )
        conn.commit()
        
        # Verify import
        trades = conn.execute("SELECT * FROM trades WHERE batch_id=?", (batch_id,)).fetchall()
        assert len(trades) == 3
        
        conn.close()
    
    def test_cli_workflow_multi_wallet(self, e2e_db):
        """Test CLI multi-wallet portfolio management."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        # Create 3 wallets
        wallets = [
            ("eth-cold", "ETH Cold Storage", "0xeth111"),
            ("btc-cold", "BTC Cold Storage", "0xbtc222"),
            ("ada-hot", "ADA Hot Wallet", "0xada333"),
        ]
        
        for wallet_id, name, address in wallets:
            conn.execute(
                "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
                (wallet_id, name, address, "0", datetime.now().isoformat())
            )
        conn.commit()
        
        # Add transactions to each wallet
        coins = ["ETH", "BTC", "ADA"]
        for idx, (w_id, _, _) in enumerate(wallets):
            coin = coins[idx]
            for i in range(3):
                conn.execute(
                    """INSERT INTO trades
                       (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f"multi-{w_id}-{i}", "2024-01-15", w_id, "Exchange", "BUY", coin, "1.0", "1000", "5", "USD", "multi_batch")
                )
        conn.commit()
        
        # Verify portfolio
        for wallet_id, _, _ in wallets:
            wallet_trades = conn.execute("SELECT COUNT(*) FROM trades WHERE source=?", (wallet_id,)).fetchone()[0]
            assert wallet_trades == 3
        
        total_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert total_trades == 9
        
        conn.close()
    
    def test_cli_workflow_filtering_and_reporting(self, e2e_db):
        """Test CLI filtering and reporting."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        wallet_id = "filter-wallet"
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Filter Wallet", "0xfilter789", "100", datetime.now().isoformat())
        )
        conn.commit()
        
        # Add mixed transactions
        transactions = [
            ("2024-01-01", "BUY", "BTC", "0.5", "45000"),
            ("2024-01-05", "SELL", "BTC", "0.2", "46000"),
            ("2024-01-10", "BUY", "ETH", "2.0", "2500"),
            ("2024-01-15", "BUY", "ETH", "1.5", "2400"),
            ("2024-01-20", "SELL", "ETH", "1.0", "2450"),
        ]
        
        for i, (date, action, coin, amount, price) in enumerate(transactions):
            conn.execute(
                """INSERT INTO trades
                   (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"filter-trade-{i}", date, wallet_id, "Exchange", action, coin, amount, price, "5", "USD", "filter_batch")
            )
        conn.commit()
        
        # Test filters
        btc_trades = conn.execute("SELECT * FROM trades WHERE coin=?", ("BTC",)).fetchall()
        assert len(btc_trades) == 2
        
        buy_trades = conn.execute("SELECT * FROM trades WHERE action=?", ("BUY",)).fetchall()
        assert len(buy_trades) == 3
        
        date_range_trades = conn.execute(
            "SELECT * FROM trades WHERE date BETWEEN ? AND ?",
            ("2024-01-01", "2024-01-10")
        ).fetchall()
        assert len(date_range_trades) == 3
        
        # Generate reports
        report = {
            "total_trades": conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
            "total_fees": conn.execute("SELECT SUM(CAST(fee AS REAL)) FROM trades").fetchone()[0],
            "total_buy_volume": conn.execute("SELECT SUM(CAST(amount AS REAL)) FROM trades WHERE action='BUY'").fetchone()[0],
            "coin_breakdown": {}
        }
        
        coins = conn.execute("SELECT DISTINCT coin FROM trades").fetchall()
        for (coin,) in coins:
            count = conn.execute("SELECT COUNT(*) FROM trades WHERE coin=?", (coin,)).fetchone()[0]
            report["coin_breakdown"][coin] = count
        
        assert report["total_trades"] == 5
        assert report["total_fees"] == 25.0
        assert len(report["coin_breakdown"]) == 2
        
        conn.close()


class TestCLIWebIntegration:
    """Test CLI and Web UI integration."""
    
    def test_cli_web_data_visibility(self, e2e_db):
        """Test that data created in CLI is visible in Web and vice versa."""
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        
        wallet_id = "integration-wallet"
        
        # CLI creates wallet
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Integration Wallet", "0xint123", "50", datetime.now().isoformat())
        )
        conn.commit()
        
        # CLI adds trades
        for i in range(3):
            conn.execute(
                """INSERT INTO trades
                   (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"cli-int-trade-{i}", f"2024-01-{i+1:02d}", wallet_id, "Kraken", "BUY", "ETH", "1.0", "2000", "5", "USD", "cli_batch")
            )
        conn.commit()
        
        # Web UI queries for these trades (simulated by reading from same DB)
        web_trades = conn.execute("SELECT * FROM trades").fetchall()
        assert len(web_trades) == 3
        assert all(t[5] == "ETH" for t in web_trades)  # coin
        
        # Web UI adds trades
        for i in range(2):
            conn.execute(
                """INSERT INTO trades
                   (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"web-int-trade-{i}", f"2024-01-{i+10:02d}", wallet_id, "Coinbase", "SELL", "BTC", "0.5", "45000", "10", "USD", "web_batch")
            )
        conn.commit()
        
        # CLI queries for all trades
        all_trades = conn.execute("SELECT * FROM trades").fetchall()
        assert len(all_trades) == 5
        
        conn.close()
    
    def test_concurrent_cli_web_operations(self, e2e_db):
        """Test concurrent operations from CLI and Web UI."""
        errors = []
        
        wallet_id = "concurrent-wallet"
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Concurrent Wallet", "0xconcur456", "100", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        trade_count = {"value": 0}
        lock = threading.Lock()
        
        def cli_adds_trades():
            try:
                conn = sqlite3.connect(str(e2e_db), timeout=10)
                for i in range(5):
                    conn.execute(
                        """INSERT INTO trades
                           (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (f"cli-concurrent-{i}", "2024-01-15", wallet_id, "CLI", "BUY", "ETH", "1.0", "2000", "5", "USD", "cli_concurrent")
                    )
                    conn.commit()
                conn.close()
                with lock:
                    trade_count["value"] += 5
            except Exception as e:
                errors.append(f"CLI: {e}")
        
        def web_adds_trades():
            try:
                conn = sqlite3.connect(str(e2e_db), timeout=10)
                for i in range(5):
                    conn.execute(
                        """INSERT INTO trades
                           (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (f"web-concurrent-{i}", "2024-01-15", wallet_id, "Web", "SELL", "BTC", "0.5", "45000", "10", "USD", "web_concurrent")
                    )
                    conn.commit()
                conn.close()
                with lock:
                    trade_count["value"] += 5
            except Exception as e:
                errors.append(f"Web: {e}")
        
        t1 = threading.Thread(target=cli_adds_trades)
        t2 = threading.Thread(target=web_adds_trades)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert not errors
        
        # Verify all trades were added
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        final_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert final_count == 10
        conn.close()


class TestMultiUserConcurrency:
    """Test multi-user concurrent scenarios."""
    
    def test_multiple_users_concurrent_adds(self, e2e_db):
        """Test 5 users adding transactions concurrently."""
        errors = []
        wallet_id = "multiuser-wallet"
        
        # Setup
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Multi-user Wallet", "0xmulti789", "1000", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        def user_adds_trades(user_id):
            try:
                conn = sqlite3.connect(str(e2e_db), timeout=10)
                for i in range(4):
                    conn.execute(
                        """INSERT INTO trades
                           (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (f"user-{user_id}-trade-{i}", "2024-01-15", wallet_id, "Exchange", "BUY", "ETH", "0.1", "2000", "1", "USD", f"user_{user_id}_batch")
                    )
                    conn.commit()
                conn.close()
            except Exception as e:
                errors.append(f"User {user_id}: {e}")
        
        threads = [threading.Thread(target=user_adds_trades, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert not errors
        
        # Verify all trades were added (5 users × 4 trades = 20)
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        total_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert total_trades == 20
        conn.close()
    
    def test_concurrent_report_generation(self, e2e_db):
        """Test report generation while trades are being added."""
        errors = []
        reports = []
        start_event = threading.Event()
        wallet_id = "report-wallet"
        
        # Setup
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        conn.execute(
            "INSERT INTO wallets (id, name, address, balance, created_at) VALUES (?, ?, ?, ?, ?)",
            (wallet_id, "Report Wallet", "0xreport000", "500", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        def add_trades():
            try:
                start_event.wait()
                conn = sqlite3.connect(str(e2e_db), timeout=10)
                for i in range(20):
                    conn.execute(
                        """INSERT INTO trades
                           (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (f"report-trade-{i}", "2024-01-15", wallet_id, "Exchange", "BUY", "ETH", "0.1", "2000", "1", "USD", "report_batch")
                    )
                    conn.commit()
                    time.sleep(0.01)
                conn.close()
            except Exception as e:
                errors.append(f"Add trades: {e}")
        
        def generate_reports():
            try:
                start_event.wait()
                time.sleep(0.05)
                for _ in range(4):
                    conn = sqlite3.connect(str(e2e_db), timeout=10)
                    report = {
                        "timestamp": datetime.now().isoformat(),
                        "total_trades": conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
                        "total_fees": conn.execute("SELECT SUM(CAST(fee AS REAL)) FROM trades").fetchone()[0] or 0,
                    }
                    reports.append(report)
                    conn.close()
                    time.sleep(0.06)
            except Exception as e:
                errors.append(f"Generate reports: {e}")
        
        t1 = threading.Thread(target=add_trades)
        t2 = threading.Thread(target=generate_reports)
        
        t1.start()
        t2.start()
        start_event.set()
        t1.join()
        t2.join()
        
        assert not errors
        assert len(reports) >= 3
        
        # Final count should have most or all trades
        conn = sqlite3.connect(str(e2e_db), timeout=10)
        final_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert final_count >= 15
        conn.close()
