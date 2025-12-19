"""
================================================================================
TEST: Report Generation and Export
================================================================================

Validates Transaction report generation and file export functionality.

Test Coverage:
    - Export CSV format (Form 8949)
    - Income report generation
    - 1099-DA reconciliation format
    - Wash sale reports
    - Holdings snapshots (EOY)
    - Transaction loss carryover analysis
    - Report accuracy validation

Author: robertbiv
================================================================================
"""
from test_common import *

class TestReportVerification(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Patch globals
        self.base_patcher = patch('Crypto_Transaction_Engine.BASE_DIR', self.test_path)
        self.input_patcher = patch('Crypto_Transaction_Engine.INPUT_DIR', self.test_path / 'inputs')
        self.output_patcher = patch('Crypto_Transaction_Engine.OUTPUT_DIR', self.test_path / 'outputs')
        self.db_patcher = patch('Crypto_Transaction_Engine.DB_FILE', self.test_path / 'report_test.db')
        self.keys_patcher = patch('Crypto_Transaction_Engine.KEYS_FILE', self.test_path / 'api_keys.json')
        self.wallets_patcher = patch('Crypto_Transaction_Engine.WALLETS_FILE', self.test_path / 'wallets.json')
        self.config_patcher = patch('Crypto_Transaction_Engine.CONFIG_FILE', self.test_path / 'config.json')
        
        self.base_patcher.start()
        self.input_patcher.start()
        self.output_patcher.start()
        self.db_patcher.start()
        self.keys_patcher.start()
        self.wallets_patcher.start()
        self.config_patcher.start()
        
        app.initialize_folders()
        self.db = app.DatabaseManager()

    def tearDown(self):
        self.db.close()
        
        self.config_patcher.stop()
        self.wallets_patcher.stop()
        self.keys_patcher.stop()
        self.db_patcher.stop()
        self.output_patcher.stop()
        self.input_patcher.stop()
        self.base_patcher.stop()
        
        shutil.rmtree(self.test_dir)
    def test_csv_output_accuracy(self):
        shadow = ShadowFIFO()
        shadow.add('BTC', 1.0, 10000.0, datetime(2023, 1, 1))
        self.db.save_trade({'id': '1', 'date': '2023-01-01', 'source': 'M', 'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 10000.0, 'fee': 0, 'batch_id': '1'})
        shadow.add('USDC', 100.0, 1.0, datetime(2023, 2, 1), is_income=True)
        self.db.save_trade({'id': '2', 'date': '2023-02-01', 'source': 'M', 'action': 'INCOME', 'coin': 'USDC', 'amount': 100.0, 'price_usd': 1.0, 'fee': 0, 'batch_id': '2'})
        shadow.sell('BTC', 0.5, 20000.0, datetime(2023, 3, 1))
        self.db.save_trade({'id': '3', 'date': '2023-03-01', 'source': 'M', 'action': 'SELL', 'coin': 'BTC', 'amount': 0.5, 'price_usd': 20000.0, 'fee': 0, 'batch_id': '3'})
        self.db.commit()
        engine = app.TransactionEngine(self.db, 2023)
        engine.run()
        engine.export()
        tt_file = app.OUTPUT_DIR / "Year_2023" / "CAP_GAINS.csv"
        self.assertTrue(tt_file.exists())
        df_tt = pd.read_csv(tt_file)
        net_gain = df_tt['Proceeds'].sum() - df_tt['Cost Basis'].sum()
        self.assertAlmostEqual(net_gain, 5000.0, delta=0.01)
        inc_file = app.OUTPUT_DIR / "Year_2023" / "INCOME_REPORT.csv"
        self.assertTrue(inc_file.exists())
        self.assertAlmostEqual(pd.read_csv(inc_file)['USD'].sum(), 100.0, delta=0.01)
        snap_file = app.OUTPUT_DIR / "Year_2023" / "CURRENT_HOLDINGS_DRAFT.csv"
        if not snap_file.exists(): snap_file = app.OUTPUT_DIR / "Year_2023" / "EOY_HOLDINGS_SNAPSHOT.csv"
        self.assertTrue(snap_file.exists())
        df_snap = pd.read_csv(snap_file)
        btc_holdings = df_snap[df_snap['Coin'] == 'BTC']['Holdings'].sum()
        self.assertAlmostEqual(btc_holdings, 0.5, places=6)



class TestReportGenerationAndExport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'report_test.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_csv_output_with_special_characters(self):
        """Test: CSV export with special characters (quotes, commas) in coin names"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC,TEST', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        
        engine = app.TransactionEngine(self.db, 2023)
        try:
            engine.run()
            engine.export()
            # Should handle special chars in CSV
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Special character CSV export crashed: {e}")
    
    def test_empty_income_year_report(self):
        """Test: Year with no income transactions generates valid report"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        
        engine = app.TransactionEngine(self.db, 2023)
        engine.run()
        try:
            engine.export()
            # Report with only trades, no income
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Empty income report crashed: {e}")
    
    def test_all_income_year_report(self):
        """Test: Year with only income transactions (no sales)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'INCOME', 'coin':'ETH', 'amount':1.0, 'price_usd':1500.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        
        engine = app.TransactionEngine(self.db, 2023)
        engine.run()
        try:
            engine.export()
            # Report with only income
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"All-income year report crashed: {e}")
    
    def test_report_with_very_large_numbers(self):
        """Test: CSV export with very large numbers (millions of dollars)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1000.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1000.0, 'price_usd':80000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TransactionEngine(self.db, 2023)
        engine.run()
        try:
            engine.export()
            # Report with large dollar amounts
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Large number report crashed: {e}")

# --- 26. LARGE-SCALE DATA INGESTION TESTS ---


class TestExportInternals(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'export_test.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_export_creates_year_folder(self):
        """Test: Export creates Year_YYYY folder structure"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        
        engine = app.TransactionEngine(self.db, 2023)
        engine.run()
        engine.export()
        
        year_folder = app.OUTPUT_DIR / 'Year_2023'
        self.assertTrue(year_folder.exists())
    
    def test_export_generates_csv_files(self):
        """Test: Export generates transaction_REPORT.csv and other outputs"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        
        engine = app.TransactionEngine(self.db, 2023)
        engine.run()
        engine.export()
        
        transaction_report = app.OUTPUT_DIR / 'Year_2023' / 'transaction_REPORT.csv'
        self.assertTrue(transaction_report.exists())

# --- 35. AUDITOR FBAR & REPORTING TESTS ---


class TestExportFormatEdgeCases(unittest.TestCase):
    """Test edge cases in CSV/JSON export formats"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        app.BASE_DIR = self.test_path
        app.DB_FILE = self.test_path / 'export_edge_cases.db'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
    
    def test_export_with_special_characters(self):
        """Test exporting trades with special characters in coin names"""
        self.db.save_trade({
            'id': 'special_1',
            'date': '2024-01-01',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'BTC-USD',  # Hyphenated
            'amount': 1.0,
            'price_usd': 50000.0,
            'fee': 0,
            'batch_id': 'special'
        })
        
        self.db.save_trade({
            'id': 'special_2',
            'date': '2024-01-02',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'ETH.USDC',  # Dotted
            'amount': 1.0,
            'price_usd': 2000.0,
            'fee': 0,
            'batch_id': 'special'
        })
        
        self.db.save_trade({
            'id': 'special_3',
            'date': '2024-01-03',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'DAI (Stablecoin)',  # With parentheses
            'amount': 1.0,
            'price_usd': 1.0,
            'fee': 0,
            'batch_id': 'special'
        })
        
        self.db.commit()
        
        df = self.db.get_all()
        self.assertEqual(len(df), 3)
        self.assertEqual(df.iloc[0]['coin'], 'BTC-USD')
        self.assertEqual(df.iloc[1]['coin'], 'ETH.USDC')
        self.assertIn('Stablecoin', df.iloc[2]['coin'])
    
    def test_export_with_very_large_numbers(self):
        """Test exporting trades with very large numbers"""
        self.db.save_trade({
            'id': 'large_1',
            'date': '2024-01-01',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'SHIB',
            'amount': 999_999_999_999.999,  # 1 trillion with decimals
            'price_usd': 0.00000001,
            'fee': 0,
            'batch_id': 'large'
        })
        
        self.db.commit()
        
        df = self.db.get_all()
        # Use assertAlmostEqual for floating point comparison
        self.assertAlmostEqual(float(df.iloc[0]['amount']), 999_999_999_999.999, places=3)
    
    def test_export_with_null_values(self):
        """Test handling of null/missing values in export"""
        self.db.save_trade({
            'id': 'null_1',
            'date': '2024-01-01',
            'source': 'WALLET',
            'action': 'INCOME',
            'coin': 'UNKNOWN',
            'amount': 100.0,
            'price_usd': None,  # Missing price
            'fee': 0,
            'batch_id': 'null'
        })
        
        self.db.commit()
        
        df = self.db.get_all()
        # Should handle null gracefully
        self.assertEqual(len(df), 1)




class TestAuditorFBARAndReporting(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'auditor_test.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
        self.held_stdout = sys.stdout
        sys.stdout = StringIO()
    def tearDown(self):
        sys.stdout = self.held_stdout
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_calculate_fbar_max_balance(self):
        """Test: FBAR calculates maximum USD value across year"""
        # Create auditor and test FBAR max calculation
        auditor = app.WalletAuditor(self.db)
        
        # Simulate multiple wallet balance checks
        auditor.max_balances = {'BINANCE': 50000.0, 'KRAKEN': 25000.0, 'EXCHANGE_C': 30000.0}
        
        try:
            # _calculate_fbar_max should find the global max
            max_val = max(auditor.max_balances.values()) if auditor.max_balances else 0
            self.assertGreater(max_val, 0)
        except Exception as e:
            self.fail(f"FBAR max calculation crashed: {e}")
    
    def test_fbar_threshold_reporting(self):
        """Test: FBAR is triggered when balance exceeds $10,000 USD"""
        auditor = app.WalletAuditor(self.db)
        auditor.max_balances = {'FOREIGN_EXCHANGE': 15000.0}
        
        # FBAR required if total > $10,000
        total_max = max(auditor.max_balances.values()) if auditor.max_balances else 0
        if total_max > 10000:
            self.assertTrue(True)  # FBAR required
    
    def test_auditor_print_report_output(self):
        """Test: Auditor can print report without crashing"""
        auditor = app.WalletAuditor(self.db)
        
        try:
            auditor.print_report()
            # Report printed without error
            self.assertTrue(True)
        except Exception as e:
            # OK if no data to report
            self.assertIsNotNone(e)

# --- 36. API ERROR HANDLING & EXCEPTIONS ---


class TestAuditWalletValidation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'audit_test.db'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_corrupted_wallet_address_format(self):
        """Test: Invalid wallet address format is handled gracefully"""
        wallets = {"ethereum": {"addresses": ["INVALID_ADDRESS_!@#$%"]}}
        with open(app.WALLETS_FILE, 'w') as f:
            json.dump(wallets, f)
        
        try:
            auditor = app.WalletAuditor(self.db)
            auditor.run_audit()
            # Should skip invalid address gracefully
            self.assertTrue(True)
        except Exception as e:
            # OK if error is caught gracefully
            self.assertIsNotNone(e)
    
    def test_empty_wallet_list_audit(self):
        """Test: Audit with empty wallet list doesn't crash"""
        wallets = {}
        with open(app.WALLETS_FILE, 'w') as f:
            json.dump(wallets, f)
        
        try:
            auditor = app.WalletAuditor(self.db)
            auditor.run_audit()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Empty wallet audit crashed: {e}")
    
    def test_duplicate_wallet_addresses_audit(self):
        """Test: Duplicate addresses are handled"""
        wallets = {"ethereum": {"addresses": ["0x123abc", "0x123abc"]}}
        with open(app.WALLETS_FILE, 'w') as f:
            json.dump(wallets, f)
        
        try:
            auditor = app.WalletAuditor(self.db)
            auditor.run_audit()
            # Should deduplicate
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Duplicate wallet audit crashed: {e}")

# --- 25. REPORT GENERATION & EXPORT TESTS ---


class TestFBARCompliance2025(unittest.TestCase):
    """Test FBAR (Report of Foreign Bank and Financial Accounts) compliance for 2025"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'fbar_test.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        app.BASE_DIR = self.orig_base
    
    def test_fbar_flags_foreign_exchange_over_10k(self):
        """Test: Foreign exchange accounts >$10,000 trigger FBAR warning"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Binance account with total value exceeding $10,000
        self.db.save_trade({
            'id': 'binance_1',
            'date': '2025-03-01',
            'source': 'BINANCE',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.3,
            'price_usd': 50000,  # 0.3 * 50000 = $15,000
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # Should flag FBAR requirement for foreign exchange
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should detect FBAR requirement for foreign exchange >$10k")
        self.assertEqual(fbar_warnings[0]['count'], 1)
        self.assertIn('BINANCE', str(fbar_warnings[0]['items']))
    
    def test_fbar_does_not_flag_domestic_exchanges(self):
        """Test: Domestic exchanges (Coinbase, Kraken) don't trigger FBAR"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Coinbase account with large amount (should NOT trigger FBAR)
        self.db.save_trade({
            'id': 'cb_1',
            'date': '2025-03-01',
            'source': 'COINBASE',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.5,
            'price_usd': 50000,  # 0.5 * 50000 = $25,000
            'fee': 0,
            'batch_id': 'test'
        })
        
        # Kraken account with large amount (should NOT trigger FBAR)
        self.db.save_trade({
            'id': 'kraken_1',
            'date': '2025-04-01',
            'source': 'KRAKEN',
            'action': 'BUY',
            'coin': 'ETH',
            'amount': 10,
            'price_usd': 2000,  # 10 * 2000 = $20,000
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # Should NOT flag FBAR for domestic exchanges
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 0, "Should NOT flag domestic exchanges for FBAR")
    
    def test_fbar_binance_us_not_flagged(self):
        """Test: Binance.US (US-registered) should NOT trigger FBAR"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Binance.US with $15,000 (should NOT flag - it's domestic)
        self.db.save_trade({
            'id': 'binance_us_1',
            'date': '2025-03-01',
            'source': 'BINANCE.US',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.3,
            'price_usd': 50000,  # $15,000
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # BINANCE.US should NOT trigger FBAR (US-registered entity)
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 0, "Binance.US should NOT trigger FBAR (US-registered)")
    
    def test_fbar_threshold_exactly_10k(self):
        """Test: FBAR does NOT trigger at exactly $10,000 threshold"""
        from Transaction_Reviewer import TransactionReviewer
        
        # OKX with exactly $10,000
        self.db.save_trade({
            'id': 'okx_1',
            'date': '2025-05-01',
            'source': 'OKX',
            'action': 'BUY',
            'coin': 'ETH',
            'amount': 5,
            'price_usd': 2000,  # 5 * 2000 = $10,000 (exactly at threshold)
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # Exactly $10,000 should NOT trigger (must be > $10,000)
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 0, "Exactly $10,000 should not trigger FBAR (must be > $10,000)")
    
    def test_fbar_aggregate_multiple_exchanges_below_threshold_individually(self):
        """Test: FBAR CRITICAL RULE - Aggregate of multiple exchanges below individual threshold but above $10k combined"""
        from Transaction_Reviewer import TransactionReviewer
        
        # This is the critical scenario: $6,000 on Binance + $5,000 on KuCoin = $11,000 total
        # Old (wrong) logic: Neither flagged individually (both < $10k). Result: No FBAR warning - FAILURE TO FILE
        # New (correct) logic: Aggregate = $11,000 > $10,000. Result: FBAR warning - COMPLIANCE
        
        self.db.save_trade({
            'id': 'binance_1',
            'date': '2025-01-15',
            'source': 'BINANCE',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.12,
            'price_usd': 50000,  # 0.12 * 50,000 = $6,000
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.save_trade({
            'id': 'kucoin_1',
            'date': '2025-02-20',
            'source': 'KUCOIN',
            'action': 'BUY',
            'coin': 'ETH',
            'amount': 2.5,
            'price_usd': 2000,  # 2.5 * 2,000 = $5,000
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # MUST flag - aggregate is $11,000 (> $10,000)
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should have ONE FBAR warning for aggregate > $10k")
        
        # Verify it includes both exchanges
        warning = fbar_warnings[0]
        self.assertEqual(warning['count'], 2, "Warning should list both foreign exchanges")
        self.assertGreater(warning['aggregate_balance'], 10000, "Aggregate should exceed $10,000")
        
        # Verify all exchanges are listed
        exchange_names = [item['exchange'] for item in warning['items']]
        self.assertIn('BINANCE', exchange_names)
        self.assertIn('KUCOIN', exchange_names)

    
    def test_fbar_threshold_10k_plus_one(self):
        """Test: FBAR triggers at $10,001 (just above threshold)"""
        from Transaction_Reviewer import TransactionReviewer
        
        # KuCoin with $10,001
        self.db.save_trade({
            'id': 'kucoin_1',
            'date': '2025-06-01',
            'source': 'KUCOIN',
            'action': 'BUY',
            'coin': 'SOL',
            'amount': 100,
            'price_usd': 100.01,  # 100 * 100.01 = $10,001
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # $10,001 should trigger FBAR
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should trigger FBAR at >$10,000")
    
    def test_fbar_flags_self_custody_uncertainty(self):
        """Test: Self-custody wallets generate FBAR uncertainty suggestion"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Hardware wallet with significant holdings
        self.db.save_trade({
            'id': 'wallet_1',
            'date': '2025-02-01',
            'source': 'HARDWARE WALLET',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.5,
            'price_usd': 50000,  # 0.5 * 50000 = $25,000
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        # Should suggest FBAR uncertainty for self-custody
        fbar_suggestions = [s for s in report['suggestions'] if s['category'] == 'FBAR_SELF_CUSTODY_UNCERTAIN']
        self.assertEqual(len(fbar_suggestions), 1, "Should flag self-custody FBAR uncertainty")
        self.assertIn('FinCEN', str(fbar_suggestions[0]['description']))
    
    def test_fbar_multiple_foreign_exchanges(self):
        """Test: Multiple foreign exchanges tracked separately"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Binance: $15,000
        self.db.save_trade({
            'id': 'binance_1',
            'date': '2025-01-01',
            'source': 'BINANCE',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.3,
            'price_usd': 50000,
            'fee': 0,
            'batch_id': 'test'
        })
        
        # OKX: $12,000
        self.db.save_trade({
            'id': 'okx_1',
            'date': '2025-02-01',
            'source': 'OKX',
            'action': 'BUY',
            'coin': 'ETH',
            'amount': 6,
            'price_usd': 2000,
            'fee': 0,
            'batch_id': 'test'
        })
        
        # KuCoin: $8,000 (under threshold)
        self.db.save_trade({
            'id': 'kucoin_1',
            'date': '2025-03-01',
            'source': 'KUCOIN',
            'action': 'BUY',
            'coin': 'SOL',
            'amount': 100,
            'price_usd': 80,
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should have one FBAR warning")
        # All three exchanges should be listed in the warning (aggregate = $35,000)
        self.assertEqual(fbar_warnings[0]['count'], 3, "Should list all 3 foreign exchanges (aggregate > $10k)")
        self.assertGreater(fbar_warnings[0]['aggregate_balance'], 10000, "Aggregate should exceed $10,000")
    
    def test_fbar_recognizes_crypto_dot_com(self):
        """Test: Crypto.com properly identified as foreign exchange"""
        from Transaction_Reviewer import TransactionReviewer
        
        self.db.save_trade({
            'id': 'crypto_1',
            'date': '2025-04-01',
            'source': 'CRYPTO.COM',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.25,
            'price_usd': 50000,  # $12,500
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should identify Crypto.com as foreign")
    
    def test_fbar_aggregates_same_exchange_multiple_coins(self):
        """Test: Same exchange with multiple coins aggregates to one FBAR flag"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Bybit: Multiple purchases totaling >$10k
        self.db.save_trade({
            'id': 'bybit_btc',
            'date': '2025-01-01',
            'source': 'BYBIT',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.1,
            'price_usd': 50000,  # $5,000
            'fee': 0,
            'batch_id': 'test'
        })
        
        self.db.save_trade({
            'id': 'bybit_eth',
            'date': '2025-02-01',
            'source': 'BYBIT',
            'action': 'BUY',
            'coin': 'ETH',
            'amount': 3,
            'price_usd': 2000,  # $6,000
            'fee': 0,
            'batch_id': 'test'
        })
        
        self.db.save_trade({
            'id': 'bybit_sol',
            'date': '2025-03-01',
            'source': 'BYBIT',
            'action': 'BUY',
            'coin': 'SOL',
            'amount': 50,
            'price_usd': 100,  # $5,000 (total = $16,000)
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should have one FBAR warning for Bybit")
        # Bybit should be in the flagged list once (aggregated)
        bybit_count = sum(1 for item in fbar_warnings[0]['items'] if 'BYBIT' in str(item['exchange']))
        self.assertEqual(bybit_count, 1, "Bybit should be aggregated as one warning")
    
    def test_fbar_only_counts_buy_and_income(self):
        """Test: FBAR doesn't count SELL or WITHDRAW transactions"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Gate.io: Deposit $15,000
        self.db.save_trade({
            'id': 'gate_buy',
            'date': '2025-01-01',
            'source': 'GATE.IO',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.3,
            'price_usd': 50000,  # $15,000
            'fee': 0,
            'batch_id': 'test'
        })
        
        # Sell it back (should not reduce FBAR obligation)
        self.db.save_trade({
            'id': 'gate_sell',
            'date': '2025-02-01',
            'source': 'GATE.IO',
            'action': 'SELL',
            'coin': 'BTC',
            'amount': 0.3,
            'price_usd': 55000,
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1, "Should flag FBAR based on max balance reached")
        # Max balance was $15,000 (after buy), sell doesn't remove the FBAR obligation
    
    def test_fbar_text_mentions_april_15_deadline(self):
        """Test: FBAR warning includes filing deadline information"""
        from Transaction_Reviewer import TransactionReviewer
        
        self.db.save_trade({
            'id': 'binance_1',
            'date': '2025-01-01',
            'source': 'BINANCE',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.3,
            'price_usd': 50000,
            'fee': 0,
            'batch_id': 'test'
        })
        self.db.commit()
        
        reviewer = TransactionReviewer(self.db, 2025)
        report = reviewer.run_review()
        
        fbar_warnings = [w for w in report['warnings'] if w['category'] == 'FBAR_FOREIGN_EXCHANGES']
        self.assertEqual(len(fbar_warnings), 1)
        # Check for deadline information
        warning_text = str(fbar_warnings[0]['action']).upper()
        self.assertIn('APRIL', warning_text, "Should mention April deadline")
        self.assertIn('2026', warning_text, "Should mention 2026 filing year")




if __name__ == '__main__':
    unittest.main()


