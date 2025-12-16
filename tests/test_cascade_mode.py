"""Tests for Cascade Mode Recalculation"""
from test_common import *
import auto_runner
import sys
from io import StringIO
from contextlib import redirect_stdout

class TestCascadeMode(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        self.orig_db = app.DB_FILE
        self.orig_output = app.OUTPUT_DIR
        self.orig_config = app.CONFIG_FILE
        
        # Redirect app paths to temp dir
        app.BASE_DIR = self.test_path
        app.DB_FILE = self.test_path / 'crypto_master.db'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.INPUT_DIR = self.test_path / 'inputs'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        
        self.db = app.DatabaseManager()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
        app.DB_FILE = self.orig_db
        app.OUTPUT_DIR = self.orig_output
        app.CONFIG_FILE = self.orig_config

    def test_cascade_runs_all_years(self):
        """Test that cascade mode runs reports for all years starting from the first transaction."""
        
        # 1. Setup Data spanning 3 years
        # 2023: Buy 1 BTC @ 10k
        self.db.save_trade({
            'id': '2023_buy', 'date': '2023-01-01 12:00:00', 'source': 'Manual', 
            'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 10000.0, 'fee': 0, 'batch_id': '1'
        })
        
        # 2024: Sell 0.5 BTC @ 20k (Gain 5k)
        self.db.save_trade({
            'id': '2024_sell', 'date': '2024-06-01 12:00:00', 'source': 'Manual', 
            'action': 'SELL', 'coin': 'BTC', 'amount': 0.5, 'price_usd': 20000.0, 'fee': 0, 'batch_id': '2'
        })
        
        # 2025: Sell 0.5 BTC @ 30k (Gain 10k)
        self.db.save_trade({
            'id': '2025_sell', 'date': '2025-01-01 12:00:00', 'source': 'Manual', 
            'action': 'SELL', 'coin': 'BTC', 'amount': 0.5, 'price_usd': 30000.0, 'fee': 0, 'batch_id': '3'
        })
        self.db.commit()
        
        # Configure current year as 2025
        with open(app.CONFIG_FILE, 'w') as f:
            json.dump({'tax_year': 2025}, f)

        # 2. Run Auto_Runner with --cascade
        # We need to patch sys.argv to simulate the command line flag
        with patch('sys.argv', ['Auto_Runner.py', '--cascade']):
            Auto_Runner.run_automation()

        # 3. Verify Output
        # Check that output folders exist for all years
        self.assertTrue((app.OUTPUT_DIR / 'Year_2023').exists(), "Year 2023 folder missing")
        self.assertTrue((app.OUTPUT_DIR / 'Year_2024').exists(), "Year 2024 folder missing")
        self.assertTrue((app.OUTPUT_DIR / 'Year_2025').exists(), "Year 2025 folder missing")

        # 4. Verify Tax Logic Integrity
        # Check 2024 Report for correct gain
        # Cost basis for 0.5 BTC should be 5000 (half of 10k)
        # Proceeds: 10000 (0.5 * 20k)
        # Gain: 5000
        report_2024 = app.OUTPUT_DIR / 'Year_2024' / 'TURBOTAX_CAP_GAINS.csv'
        self.assertTrue(report_2024.exists(), "2024 Capital Gains report missing")
        
        df_2024 = pd.read_csv(report_2024)
        # Calculate total gain
        df_2024['Gain'] = df_2024['Proceeds'] - df_2024['Cost Basis']
        total_gain_2024 = df_2024['Gain'].sum()
        self.assertAlmostEqual(total_gain_2024, 5000.0, delta=1.0)

        # Check 2025 Report
        # Cost basis for remaining 0.5 BTC should be 5000
        # Proceeds: 15000 (0.5 * 30k)
        # Gain: 10000
        report_2025 = app.OUTPUT_DIR / 'Year_2025' / 'TURBOTAX_CAP_GAINS.csv'
        self.assertTrue(report_2025.exists(), "2025 Capital Gains report missing")
        
        df_2025 = pd.read_csv(report_2025)
        df_2025['Gain'] = df_2025['Proceeds'] - df_2025['Cost Basis']
        total_gain_2025 = df_2025['Gain'].sum()
        self.assertAlmostEqual(total_gain_2025, 10000.0, delta=1.0)

    def test_standard_mode_skips_old_years(self):
        """Test that standard mode (no cascade) does NOT re-run old finalized years."""
        
        # 1. Setup Data
        self.db.save_trade({
            'id': '2023_buy', 'date': '2023-01-01 12:00:00', 'source': 'Manual', 
            'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 10000.0, 'fee': 0, 'batch_id': '1'
        })
        self.db.commit()
        
        # Configure current year as 2025
        with open(app.CONFIG_FILE, 'w') as f:
            json.dump({'tax_year': 2025}, f)

        # Fake a finalized 2024 snapshot so it skips 2024
        year_2024_dir = app.OUTPUT_DIR / 'Year_2024'
        year_2024_dir.mkdir(parents=True)
        (year_2024_dir / 'EOY_HOLDINGS_SNAPSHOT.csv').write_text("dummy")

        # 2. Run Auto_Runner WITHOUT --cascade
        with patch('sys.argv', ['Auto_Runner.py']):
            Auto_Runner.run_automation()

        # 3. Verify Output
        # Verify 2023 folder was NOT created (skipped because it's old and not cascade)
        self.assertFalse((app.OUTPUT_DIR / 'Year_2023').exists(), "Year 2023 should not be processed in standard mode")
        
        # Verify 2025 (current year) WAS created
        self.assertTrue((app.OUTPUT_DIR / 'Year_2025').exists(), "Year 2025 should be processed")

if __name__ == '__main__':
    unittest.main()


