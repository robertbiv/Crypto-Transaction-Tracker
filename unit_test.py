import unittest
import shutil
import tempfile
import json
import sqlite3
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Import the application logic
# We assume this file is in the same directory as Crypto_Tax_Engine.py
import Crypto_Tax_Engine as app

class TestCryptoTaxEngine(unittest.TestCase):

    def setUp(self):
        """
        Runs before EACH test. 
        Sets up a temporary directory and patches the file paths 
        so we don't accidentally overwrite the user's real data.
        """
        # 1. Create a temporary directory for this test run
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

        # 2. Patch the global path variables in the app module
        self.original_base_dir = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.ARCHIVE_DIR = self.test_path / 'processed_archive'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.LOG_DIR = self.test_path / 'outputs' / 'logs'
        app.DB_FILE = self.test_path / 'test_crypto.db'
        app.DB_BACKUP = self.test_path / 'test_crypto.db.bak'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.Global_Config = {
            "general": {"run_audit": True, "create_db_backups": False},
            "performance": {"respect_free_tier_limits": False, "api_timeout_seconds": 1},
            "logging": {"compress_older_than_days": 30}
        }

        # 3. Create necessary subfolders
        for d in [app.INPUT_DIR, app.ARCHIVE_DIR, app.OUTPUT_DIR, app.LOG_DIR]:
            d.mkdir(parents=True)

        # 4. Initialize a fresh database for testing
        self.db = app.DatabaseManager()

    def tearDown(self):
        """Runs after EACH test. Cleans up files."""
        self.db.close()
        shutil.rmtree(self.test_dir)
        # Restore original paths just in case
        app.BASE_DIR = self.original_base_dir

    # ==========================================
    # DATABASE TESTS
    # ==========================================
    def test_database_init(self):
        """Ensure the DB creates the 'trades' table correctly."""
        conn = sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades';")
        self.assertIsNotNone(cursor.fetchone(), "Trades table was not created.")
        conn.close()

    def test_save_and_retrieve_trade(self):
        """Test saving a trade and reading it back."""
        trade = {
            'id': 'TEST_001',
            'date': '2024-01-01T12:00:00',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000.0,
            'fee': 10.0,
            'batch_id': 'TEST_BATCH'
        }
        self.db.save_trade(trade)
        self.db.commit()

        df = self.db.get_all()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['coin'], 'BTC')
        self.assertEqual(df.iloc[0]['price_usd'], 50000.0)

    # ==========================================
    # TAX LOGIC TESTS (FIFO)
    # ==========================================
    def test_fifo_logic_simple_gain(self):
        """
        Scenario:
        1. Buy 1 BTC @ $100
        2. Sell 1 BTC @ $200
        Expected: Cost Basis $100, Proceeds $200, Gain $100.
        """
        # Setup trades
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':100.0, 'fee':0, 'batch_id':'B1'})
        self.db.save_trade({'id':'2', 'date':'2023-02-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':200.0, 'fee':0, 'batch_id':'B1'})
        self.db.commit()

        # Run Engine
        engine = app.TaxEngine(self.db, 2023)
        engine.run()

        # Check results
        self.assertEqual(len(engine.tt), 1, "Should have 1 taxable event")
        sale = engine.tt[0]
        self.assertEqual(sale['Proceeds'], 200.0)
        self.assertEqual(sale['Cost Basis'], 100.0)

    def test_fifo_logic_mixed_batches(self):
        """
        Scenario (FIFO):
        1. Buy 1.0 BTC @ $100 (Jan 1)
        2. Buy 1.0 BTC @ $200 (Jan 2)
        3. Sell 0.5 BTC @ $300 (Jan 3)
        
        Logic: Should sell from batch 1 ($100 price).
        Cost Basis: 0.5 * $100 = $50.
        Proceeds: 0.5 * $300 = $150.
        """
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':100.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-01-02', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':200.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-01-03', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.5, 'price_usd':300.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()

        engine = app.TaxEngine(self.db, 2023)
        engine.run()

        sale = engine.tt[0]
        self.assertEqual(sale['Proceeds'], 150.0)
        self.assertEqual(sale['Cost Basis'], 50.0) # From the $100 batch

    def test_income_tracking(self):
        """Ensure mining/staking rewards show up in Income Report."""
        self.db.save_trade({'id':'1', 'date':'2023-06-01', 'source':'STAKING', 'action':'INCOME', 'coin':'ETH', 'amount':1.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()

        engine = app.TaxEngine(self.db, 2023)
        engine.run()

        self.assertEqual(len(engine.inc), 1)
        self.assertEqual(engine.inc[0]['USD'], 1000.0)

    # ==========================================
    # INGESTION TESTS
    # ==========================================
    def test_csv_ingestion(self):
        """Test loading a CSV file into the DB."""
        # Create dummy CSV
        csv_path = app.INPUT_DIR / "test_trades.csv"
        with open(csv_path, 'w') as f:
            f.write("date,coin,amount,usd_value_at_time,fee\n")
            f.write("2023-01-01,LTC,10,50,1\n") # 10 LTC @ $50 each
        
        ingestor = app.Ingestor(self.db)
        ingestor.run_csv_scan()

        df = self.db.get_all()
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row['coin'], 'LTC')
        self.assertEqual(row['amount'], 10.0)
        self.assertEqual(row['price_usd'], 50.0)
        self.assertEqual(row['source'], 'MANUAL')

        # Check file was archived
        self.assertFalse(csv_path.exists(), "CSV should have been moved")
        self.assertTrue(any(app.ARCHIVE_DIR.iterdir()), "Archive should contain file")

    # ==========================================
    # AUDIT TESTS (MOCKED)
    # ==========================================
    @patch('requests.get')
    def test_moralis_audit_mock(self, mock_get):
        """Mock Moralis API response to verify logic without calling internet."""
        # 1. Setup Keys and Wallets
        with open(app.KEYS_FILE, 'w') as f:
            json.dump({"moralis": {"apiKey": "fake_key"}}, f)
        with open(app.WALLETS_FILE, 'w') as f:
            json.dump({"ETH": ["0x123"]}, f)

        # 2. Mock the API response
        # Moralis returns balance in Wei (integer string) inside a dict
        mock_response = MagicMock()
        mock_response.status_code = 200
        # 1 ETH = 10^18 Wei. Let's say user has 2.5 ETH
        mock_response.json.return_value = {"balance": str(int(2.5 * 10**18))} 
        mock_get.return_value = mock_response

        # 3. Setup DB expectation (User bought 3.0, but only has 2.5 on chain -> -0.5 Diff)
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'ETH', 'amount':3.0, 'price_usd':100.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()

        # 4. Run Auditor
        auditor = app.WalletAuditor(self.db)
        # Suppress logging during test
        with self.assertLogs('crypto_tax_engine', level='INFO') as cm:
            auditor.run_audit()

        # 5. Check Internal State
        # auditor.real['ETH'] should be 2.5
        self.assertEqual(auditor.real.get('ETH'), 2.5)
        
        # Check that it attempted to calculate the difference
        # DB has 3.0, Real has 2.5. Diff should be +0.5 (or -0.5 depending on perspective)
        # The logic is: DB - Chain. 3.0 - 2.5 = +0.5 missing from chain.
        # We just verify it ran correctly.

if __name__ == '__main__':
    print("--- RUNNING CRYPTO TAX ENGINE TESTS ---")
    unittest.main()