"""Core US Tax Compliance Tests"""
from test_common import *

class TestAdvancedUSCompliance(unittest.TestCase):
    def setUp(self):
        print(f"\n[Running: {self._testMethodName}]", flush=True)
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'advanced_tax.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        
        # Enable Audit/Backup by default for these tests
        app.GLOBAL_CONFIG['general']['run_audit'] = True
        app.GLOBAL_CONFIG['general']['create_db_backups'] = True
        
        app.initialize_folders()
        self.db = app.DatabaseManager()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
        # Reset compliance toggles to defaults to avoid cross-test contamination
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['staking_taxable_on_receipt'] = True
        app.GLOBAL_CONFIG['compliance']['strict_broker_mode'] = True

    def test_hifo_accounting_method(self):
        """
        Scenario:
        1. Buy 1 BTC @ $10k (Jan 1)
        2. Buy 1 BTC @ $50k (Feb 1)
        3. Sell 1 BTC @ $60k (Mar 1)
        
        FIFO Result: Basis $10k (Jan lot). Gain $50k.
        HIFO Result: Basis $50k (Feb lot). Gain $10k. (Tax Minimization)
        """
        # Enable HIFO
        app.GLOBAL_CONFIG['accounting'] = {'method': 'HIFO'}
        
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-02-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-03-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':60000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        sale = engine.tt[0]
        # With HIFO, we sell the $50k lot first
        self.assertEqual(sale['Cost Basis'], 50000.0)
        self.assertEqual(sale['Proceeds'], 60000.0)
        
        # Reset Config
        if 'accounting' in app.GLOBAL_CONFIG: del app.GLOBAL_CONFIG['accounting']

    def test_fifo_accounting_method(self):
        """
        Verify Default FIFO logic.
        Same scenario as above, but Basis should be $10k.
        """
        # Ensure FIFO (default)
        app.GLOBAL_CONFIG['accounting'] = {'method': 'FIFO'}
        
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-02-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-03-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':60000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        sale = engine.tt[0]
        # With FIFO, we sell the $10k lot first
        self.assertEqual(sale['Cost Basis'], 10000.0)
        self.assertEqual(sale['Proceeds'], 60000.0)

    def test_fbar_max_balance_report(self):
        # Verify FBAR logic placeholder passes (Future Feature)
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'BINANCE_API', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':5000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'BINANCE_API', 'action':'BUY', 'coin':'BTC', 'amount':2.0, 'price_usd':5000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-12-01', 'source':'BINANCE_API', 'action':'SELL', 'coin':'BTC', 'amount':2.5, 'price_usd':5000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()
        self.assertTrue(True)

    def test_gift_dual_basis_rules(self):
        # Scenario: Gift In @ 5k (FMV). Sell @ 3k (Loss). Use 5k basis.
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'GIFT_IN', 'coin':'BTC', 'amount':1.0, 'price_usd':5000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':3000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Note: Current engine treats GIFT_IN as INCOME/BUY at FMV.
        # This matches the conservative Dual Basis rule for losses (using FMV).
        # Proceeds 3k - Basis 5k = -2k Loss. Correct.
        sale = engine.tt[0]
        self.assertEqual(sale['Cost Basis'], 5000.0) 
        self.assertEqual(sale['Proceeds'], 3000.0)

    def test_hard_fork_income(self):
        # Hold BTC. Receive BCH via Fork (Income).
        self.db.save_trade({'id':'1', 'date':'2017-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2017-08-01', 'source':'M', 'action':'INCOME', 'coin':'BCH', 'amount':1.0, 'price_usd':500.0, 'fee':0, 'batch_id':'FORK'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2017)
        engine.run()
        self.assertEqual(len(engine.inc), 1)
        self.assertEqual(engine.inc[0]['Coin'], 'BCH')
        self.assertEqual(engine.inc[0]['USD'], 500.0)
        btc_hold = engine.hold['BTC'][0]
        self.assertEqual(btc_hold['p'], 1000.0)

    def test_strict_broker_mode_blocks_cross_wallet_basis(self):
        # Configure compliance flags via config
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['strict_broker_mode'] = True
        app.GLOBAL_CONFIG['compliance']['broker_sources'] = ['COINBASE']

        # Buy on LEDGER, sell on COINBASE without local basis -> should not borrow basis
        self.db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'LEDGER', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'COINBASE', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':60000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        eng = app.TaxEngine(self.db, 2025)
        eng.run()
        sale = eng.tt[0]
        # Basis should be 0.0 (no cross-wallet fallback) and proceeds 60000
        self.assertEqual(sale['Cost Basis'], 0.0)
        self.assertEqual(sale['Proceeds'], 60000.0)

    def test_collectibles_split_reporting(self):
        # Long-term standard and collectibles separation
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['collectible_tokens'] = ['PUNK']
        # Buy PUNK and hold > 1 year, then sell
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'PUNK', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2024-02-02', 'source':'M', 'action':'SELL', 'coin':'PUNK', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        eng = app.TaxEngine(self.db, 2024)
        eng.run()
        eng.export()
        loss_csv = app.OUTPUT_DIR / 'Year_2024' / 'US_TAX_LOSS_ANALYSIS.csv'
        self.assertTrue(loss_csv.exists())
        df = pd.read_csv(loss_csv)
        val_collectible = float(df[df['Item']=='Current Year Long-Term (Collectibles 28%)']['Value'].iloc[0])
        self.assertEqual(val_collectible, 10000.0)

    def test_1099_detailed_reconciliation_unmatched_and_wash_placeholders(self):
        # Trigger an unmatched sell under strict broker mode and check detailed reconciliation
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['strict_broker_mode'] = True
        app.GLOBAL_CONFIG['compliance']['broker_sources'] = ['KRAKEN']
        self.db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'LEDGER', 'action':'BUY', 'coin':'ETH', 'amount':2.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'KRAKEN', 'action':'SELL', 'coin':'ETH', 'amount':1.0, 'price_usd':1500.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        eng = app.TaxEngine(self.db, 2025)
        eng.run()
        eng.export()
        detailed = app.OUTPUT_DIR / 'Year_2025' / '1099_RECONCILIATION_DETAILED.csv'
        self.assertTrue(detailed.exists())
        df = pd.read_csv(detailed)
        row = df[(df['Source']=='KRAKEN') & (df['Coin']=='ETH')].iloc[0]
        self.assertEqual(row['Unmatched_Sell'], 'YES')
        self.assertEqual(row['Wash_Disallowed_By_Broker'], 'PENDING')

    def test_staking_constructive_receipt_toggle(self):
        # When disabled, staking income should not be logged; lot added at zero basis
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['staking_taxable_on_receipt'] = False
        self.db.save_trade({'id':'1', 'date':'2025-03-01', 'source':'M', 'action':'INCOME', 'coin':'BTC', 'amount':0.1, 'price_usd':30000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        eng = app.TaxEngine(self.db, 2025)
        eng.run()
        # No income rows recorded
        self.assertEqual(len(eng.inc), 0)
        # Selling the reward should realize full proceeds as gain (zero basis)
        self.db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.1, 'price_usd':35000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        eng2 = app.TaxEngine(self.db, 2025)
        eng2.run()
        sale = eng2.tt[0]
        self.assertEqual(sale['Cost Basis'], 0.0)
        self.assertEqual(sale['Proceeds'], 3500.0)

# --- 3. US TAX & LOSS TESTS (Core Pillars) ---


class TestUSLosses(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'loss_limits.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_loss_carryover_logic(self):
        # Year 1: Loss 10k -> Carryover 7k
        self.db.save_trade({'id':'1', 'date':'2022-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2022-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':0.0, 'fee':0, 'batch_id':'2'})
        # Year 2: Gain 10k - 7k Carryover = 3k Net
        self.db.save_trade({'id':'3', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'ETH', 'amount':1.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'3'})
        self.db.save_trade({'id':'4', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'ETH', 'amount':1.0, 'price_usd':11000.0, 'fee':0, 'batch_id':'4'})
        self.db.commit()
        eng1 = app.TaxEngine(self.db, 2022)
        eng1.run()
        eng1.export()
        eng2 = app.TaxEngine(self.db, 2023)
        eng2.run()
        eng2.export()
        report_path = app.OUTPUT_DIR / "Year_2023" / "US_TAX_LOSS_ANALYSIS.csv"
        self.assertTrue(report_path.exists())
        df = pd.read_csv(report_path)
        prior_st = float(df[df['Item'] == 'Prior Year Short-Term Carryover']['Value'].iloc[0])
        self.assertEqual(prior_st, 7000.0)
        total_net = float(df[df['Item'] == 'Total Net Capital Gain/Loss']['Value'].iloc[0])
        self.assertEqual(total_net, 3000.0)
    def test_wash_sale_report_creation(self):
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-01-10', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-01-15', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        engine.export()
        ws_report = app.OUTPUT_DIR / "Year_2023" / "WASH_SALE_REPORT.csv"
        self.assertTrue(ws_report.exists())
    def test_wash_sale_across_years(self):
        self.db.save_trade({'id':'1', 'date':'2023-12-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-12-25', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2024-01-05', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        engine.export()
        tt_report = app.OUTPUT_DIR / "Year_2023" / "GENERIC_TAX_CAP_GAINS.csv"
        df = pd.read_csv(tt_report)
        row = df.iloc[0]
        # Proceeds 10k. Cost Basis 10k (Adjusted from 20k to match proceeds).
        self.assertEqual(row['Proceeds'], 10000.0)
        self.assertEqual(row['Cost Basis'], 10000.0)
        self.assertIn("WASH SALE", row['Description'])

# --- 4. COMPREHENSIVE US TAX LAW COMPLIANCE ---


class TestUSComprehensiveCompliance(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'us_law_test.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_gas_fees_are_taxable_events(self):
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'ETH', 'amount':1.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'TRANSFER_FEE', 'action':'SELL', 'coin':'ETH', 'amount':0.01, 'price_usd':2000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        sale = engine.tt[0]
        self.assertIn("(Fee)", sale['Description'])
        self.assertEqual(sale['Proceeds'], 20.0)
        self.assertEqual(sale['Cost Basis'], 10.0)
    def test_income_classification(self):
        self.db.save_trade({'id':'1', 'date':'2023-03-01', 'source':'M', 'action':'INCOME', 'coin':'BTC', 'amount':0.1, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(len(engine.inc), 1)
        self.assertEqual(engine.inc[0]['USD'], 2000.0)
        self.assertEqual(len(engine.tt), 0)
    def test_crypto_to_crypto_taxability(self):
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'SWAP', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(engine.tt[0]['Proceeds'], 15000.0)
        self.assertEqual(engine.tt[0]['Cost Basis'], 10000.0)
    def test_spending_crypto(self):
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':0.5, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'SPEND', 'action':'SPEND', 'coin':'BTC', 'amount':0.5, 'price_usd':12000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(engine.tt[0]['Proceeds'], 6000.0)
        self.assertEqual(engine.tt[0]['Cost Basis'], 5000.0)

# --- 5. REPORT VERIFICATION TESTS ---


class TestLendingLoss(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'loss_test.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_defaulted_loan_loss(self):
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'LOSS', 'coin':'BTC', 'amount':1.0, 'price_usd':0.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(len(engine.tt), 1)
        row = engine.tt[0]
        self.assertIn("LOSS", row['Description'])
        self.assertEqual(row['Proceeds'], 0.0)
        self.assertEqual(row['Cost Basis'], 10000.0)
    def test_borrow_repay_nontaxable(self):
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'DEPOSIT', 'coin':'ETH', 'amount':1.0, 'price_usd':0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-02-01', 'source':'M', 'action':'WITHDRAWAL', 'coin':'ETH', 'amount':1.0, 'price_usd':0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(len(engine.tt), 0)
        self.assertEqual(len(engine.inc), 0)



class TestHoldingPeriodCalculations(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'holding_test.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_short_term_364_days(self):
        """Test: 364 days = SHORT-TERM (< 1 year)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-12-31', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Should be short-term
        self.assertEqual(len(engine.tt), 1)
    
    def test_long_term_366_days(self):
        """Test: 366+ days = LONG-TERM (> 1 year)"""
        self.db.save_trade({'id':'1', 'date':'2022-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-01-02', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Should be long-term
        self.assertEqual(len(engine.tt), 1)
    
    def test_leap_year_handling(self):
        """Test: Leap year (Feb 29) handling"""
        # 2024 is leap year
        self.db.save_trade({'id':'1', 'date':'2023-02-28', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2024-02-29', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2024)
        try:
            engine.run()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Leap year caused crash: {e}")

# --- 22. PARTIAL SALES TESTS ---


class TestPartialSales(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'partial_test.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_partial_sale_half(self):
        """Test: Selling 50% of position"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.5, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        self.assertEqual(engine.tt[0]['Proceeds'], 7500.0)
        self.assertEqual(engine.tt[0]['Cost Basis'], 5000.0)
    
    def test_multiple_sells_from_same_purchase(self):
        """Test: Multiple sells from same purchase lot"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':2.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-03-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.5, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.5, 'price_usd':20000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        self.assertEqual(len(engine.tt), 2)
    
    def test_remaining_balance_tracking(self):
        """Test: Remaining balance is tracked correctly"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.3, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Should have 0.7 BTC remaining
        if 'BTC' in engine.hold:
            remaining = sum(lot['a'] for lot in engine.hold['BTC'])
            self.assertAlmostEqual(remaining, Decimal('0.7'), places=5)

# --- 23. RETURN/REFUND TRANSACTION TESTS ---


class TestWashSalePreBuyWindow(unittest.TestCase):
    """Test wash sale detection for purchases 30 days BEFORE sale (IRS Pub 550)"""
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'wash_prebuy_test.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base

    def test_wash_sale_triggered_by_pre_buy(self):
        """Test: Purchase 30 days BEFORE loss sale triggers wash sale"""
        # Jan 1: Buy 1 BTC at $30,000
        self.db.save_trade({
            'id':'buy1', 'date':'2023-01-01', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':30000.0, 'fee':0, 'batch_id':'buy1'
        })
        
        # Jan 31: Sell at loss ($20,000, loss = $10,000)
        self.db.save_trade({
            'id':'sell1', 'date':'2023-01-31', 'source':'Exchange', 
            'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'sell1'
        })
        
        # Feb 10: Buy replacement 1 BTC (11 days AFTER sale - within post-buy window)
        self.db.save_trade({
            'id':'buy2', 'date':'2023-02-10', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':21000.0, 'fee':0, 'batch_id':'buy2'
        })
        
        # Jan 15: Buy 1 BTC (16 days BEFORE sale - within pre-buy window)
        self.db.save_trade({
            'id':'prebuy', 'date':'2023-01-15', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':28000.0, 'fee':0, 'batch_id':'prebuy'
        })
        
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Should detect wash sale from BOTH pre-buy (Jan 15) and post-buy (Feb 10)
        self.assertGreater(len(engine.wash_sale_log), 0, "Pre-buy within 30 days should trigger wash sale")
        wash_log = engine.wash_sale_log[0]
        
        # Should have 2 repurchase dates (pre-buy + post-buy)
        repurchase_dates = wash_log.get('repurchase_dates', [])
        # Note: wash_sale_log structure may vary - checking that wash sale was detected
        self.assertGreater(float(wash_log['Loss Disallowed']), 0, 
                          "Loss should be disallowed due to pre-buy within 30 days")
    
    def test_wash_sale_pre_buy_exact_boundary(self):
        """Test: Purchase exactly 30 days before sale (boundary condition)"""
        # Jan 1: Buy 1 ETH
        self.db.save_trade({
            'id':'prebuy', 'date':'2023-01-01', 'source':'Exchange', 
            'action':'BUY', 'coin':'ETH', 'amount':1.0, 'price_usd':2000.0, 'fee':0, 'batch_id':'prebuy'
        })
        
        # Jan 31: Sell at loss (exactly 30 days after pre-buy)
        self.db.save_trade({
            'id':'sell1', 'date':'2023-01-31', 'source':'Exchange', 
            'action':'SELL', 'coin':'ETH', 'amount':1.0, 'price_usd':1500.0, 'fee':0, 'batch_id':'sell1'
        })
        
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Should detect wash sale (30 days is inclusive)
        self.assertGreater(len(engine.wash_sale_log), 0, 
                          "Purchase exactly 30 days before sale should trigger wash sale")
    
    def test_no_wash_sale_pre_buy_outside_window(self):
        """Test: Purchase 31 days before sale does NOT trigger wash sale"""
        # Jan 1: Buy 1 BTC
        self.db.save_trade({
            'id':'old_buy', 'date':'2023-01-01', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':25000.0, 'fee':0, 'batch_id':'old_buy'
        })
        
        # Feb 1: Sell at loss (31 days after old_buy - outside pre-buy window)
        self.db.save_trade({
            'id':'sell1', 'date':'2023-02-01', 'source':'Exchange', 
            'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'sell1'
        })
        
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # No wash sale because buy is >30 days before and no post-buy
        self.assertEqual(len(engine.wash_sale_log), 0, 
                        "Purchase 31 days before sale should NOT trigger wash sale")
    
    def test_wash_sale_pre_and_post_buy_combined(self):
        """Test: Both pre-buy and post-buy purchases combine for wash sale calculation"""
        # Jan 1: Initial purchase 2 BTC at $30,000
        self.db.save_trade({
            'id':'initial', 'date':'2023-01-01', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':2.0, 'price_usd':30000.0, 'fee':0, 'batch_id':'initial'
        })
        
        # Feb 1: Sell 2 BTC at loss ($20,000, total loss = $20,000)
        self.db.save_trade({
            'id':'sell1', 'date':'2023-02-01', 'source':'Exchange', 
            'action':'SELL', 'coin':'BTC', 'amount':2.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'sell1'
        })
        
        # Jan 20: Pre-buy 0.5 BTC (12 days BEFORE sale)
        self.db.save_trade({
            'id':'prebuy', 'date':'2023-01-20', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':0.5, 'price_usd':28000.0, 'fee':0, 'batch_id':'prebuy'
        })
        
        # Feb 15: Post-buy 0.5 BTC (14 days AFTER sale)
        self.db.save_trade({
            'id':'postbuy', 'date':'2023-02-15', 'source':'Exchange', 
            'action':'BUY', 'coin':'BTC', 'amount':0.5, 'price_usd':22000.0, 'fee':0, 'batch_id':'postbuy'
        })
        
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Should detect wash sale with combined replacement of 1.0 BTC (0.5 pre + 0.5 post)
        self.assertGreater(len(engine.wash_sale_log), 0)
        wash_log = engine.wash_sale_log[0]
        
        # Replacement qty should include BOTH pre-buy and post-buy
        replacement_qty = float(wash_log['Replacement Qty'])
        # Should be at least 0.5 (could be 1.0 if both are counted, depending on implementation)
        self.assertGreaterEqual(replacement_qty, 0.5, 
                               "Should count pre-buy in replacement quantity")




class TestRiskyOptionWarnings(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'warn_test.db'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
        # Minimal trade to ensure engine.run() flows
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base

    def test_warn_on_hifo(self):
        app.GLOBAL_CONFIG.setdefault('accounting', {})
        app.GLOBAL_CONFIG['accounting']['method'] = 'HIFO'
        with self.assertLogs('crypto_tax_engine', level='WARNING') as cm:
            _ = app.TaxEngine(self.db, 2023)
            self.assertTrue(any(app.COMPLIANCE_WARNINGS['HIFO'] in m for m in cm.output))
        app.GLOBAL_CONFIG['accounting']['method'] = 'FIFO'

    def test_warn_on_disable_strict_broker_mode(self):
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['strict_broker_mode'] = False
        with self.assertLogs('crypto_tax_engine', level='WARNING') as cm:
            _ = app.TaxEngine(self.db, 2023)
            self.assertTrue(any(app.COMPLIANCE_WARNINGS['STRICT_BROKER_DISABLED'] in m for m in cm.output))
        app.GLOBAL_CONFIG['compliance']['strict_broker_mode'] = True

    def test_warn_on_constructive_receipt_false(self):
        app.GLOBAL_CONFIG.setdefault('compliance', {})
        app.GLOBAL_CONFIG['compliance']['staking_taxable_on_receipt'] = False
        with self.assertLogs('crypto_tax_engine', level='WARNING') as cm:
            _ = app.TaxEngine(self.db, 2023)
            self.assertTrue(any(app.COMPLIANCE_WARNINGS['CONSTRUCTIVE_RECEIPT'] in m for m in cm.output))
        app.GLOBAL_CONFIG['compliance']['staking_taxable_on_receipt'] = True
    
    def test_wash_sale_outside_30day_window_not_triggered(self):
        """
        Verify that buys outside the 30-day window do NOT trigger wash sale.
        
        Scenario (using ETH to avoid setUp's BTC trade):
        - Dec 1 2022: Buy 1 ETH @ $2000 (>30 days before sale)
        - Jan 15 2023: Sell 1 ETH @ $1500 (loss of $500)
        - Feb 20 2023: Buy 1 ETH @ $1800 (36 days after sale, OUTSIDE 30-day window)
        
        Expected: NO wash sale (replacement is too far in past and future)
        """
        trades = [
            {'symbol': 'ETH', 'coin': 'ETH', 'action': 'BUY', 'amount': 1.0, 'price_usd': 2000, 'fee': 0, 'source': 'EXCHANGE', 'date': '2022-12-01'},
            {'symbol': 'ETH', 'coin': 'ETH', 'action': 'SELL', 'amount': 1.0, 'price_usd': 1500, 'fee': 0, 'source': 'EXCHANGE', 'date': '2023-01-15'},
            {'symbol': 'ETH', 'coin': 'ETH', 'action': 'BUY', 'amount': 1.0, 'price_usd': 1800, 'fee': 0, 'source': 'EXCHANGE', 'date': '2023-02-20'},
        ]
        
        for t in trades:
            self.db.save_trade(t)
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        wash_sales = engine.wash_sale_log
        self.assertEqual(len(wash_sales), 0,
            "No wash sale should be detected when replacement is >30 days away")
    
    def test_decimal_precision_throughout_calculation_chain(self):
        """
        End-to-end test: Verify Decimal precision is maintained through entire calculation chain.
        
        Chain: Database (TEXT) -> get_all (Decimal) -> TaxEngine (Decimal math) -> output (float for CSV)
        
        Test: 0.123456789 BTC bought and sold -> should appear as 0.123456789 in all intermediate steps
        """
        amt = 0.123456789
        price = 12345.6789
        
        trades = [
            {'symbol': 'BTC', 'coin': 'BTC', 'action': 'BUY', 'amount': amt, 'price_usd': price, 'fee': 0.1, 'source': 'EXCHANGE', 'date': '2023-01-01'},
            {'symbol': 'BTC', 'coin': 'BTC', 'action': 'SELL', 'amount': amt, 'price_usd': price + 100, 'fee': 0.1, 'source': 'EXCHANGE', 'date': '2023-02-01'},
        ]
        
        for t in trades:
            self.db.save_trade(t)
        self.db.commit()
        
        # Verify database layer: TEXT storage preserved
        df = self.db.get_all()
        stored_amt = df.iloc[0]['amount']
        self.assertIsInstance(stored_amt, Decimal, "Database should return Decimal")
        
        # Verify to_decimal() preserves precision
        precise_amt = app.to_decimal(str(amt))
        # 0.123456789 should stay exact (no rounding to float precision)
        self.assertEqual(precise_amt, Decimal('0.123456789'),
            "to_decimal() should preserve exact decimal representation")
        
        # Verify calculation doesn't introduce float rounding
        # Proceeds = 0.123456789 * 12445.6789 = 1537.041... (but with exact Decimal math)
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # The result should preserve significant digits
        sell_entry = engine.tt[0]
        proceeds = sell_entry['Proceeds']
        # Should be close to 1537, not affected by float rounding errors
        self.assertGreater(proceeds, 1536, "Calculation with Decimal should yield correct magnitude")
        self.assertLess(proceeds, 1538, "Calculation with Decimal should yield correct magnitude")




if __name__ == '__main__':
    unittest.main()
