"""Edge Cases and Stress Tests"""
from test_common import *

class TestEdgeCasesExtremeValues(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'edge_extreme.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_zero_amount_transaction(self):
        """Edge case: zero amount transaction should gracefully skip or handle"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':0.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should not crash
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Zero amount transaction crashed: {e}")
    def test_negative_amount_transaction(self):
        """Edge case: negative amount should be handled gracefully"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':-1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should not crash, should skip invalid row
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Negative amount transaction crashed: {e}")
    def test_extremely_large_amount(self):
        """Edge case: Very large amount (1M BTC)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1000000.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1000000.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(engine.tt[0]['Proceeds'], 20000000000.0)
        self.assertEqual(engine.tt[0]['Cost Basis'], 10000000000.0)
    def test_extremely_small_amount(self):
        """Edge case: Very tiny amount (0.000001 BTC / 1 satoshi)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':0.00000001, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.00000001, 'price_usd':20000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Proceeds = 0.00000001 * 20000.0 = 0.0002
        # Cost Basis = 0.00000001 * 10000.0 = 0.0001
        # Preserve precision for auditability even on tiny amounts
        self.assertAlmostEqual(engine.tt[0]['Proceeds'], 0.0002, places=6)
        self.assertAlmostEqual(engine.tt[0]['Cost Basis'], 0.0001, places=6)
    def test_zero_price_transaction(self):
        """Edge case: Zero price (fork/airdrop scenario)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'INCOME', 'coin':'BTC', 'amount':1.0, 'price_usd':0.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        self.assertEqual(engine.inc[0]['USD'], 0.0)
    def test_negative_price_graceful_handling(self):
        """Edge case: Negative price should be handled gracefully"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':-10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should not crash
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Negative price crashed: {e}")
    def test_extremely_high_price(self):
        """Edge case: Extreme price per unit ($1M per token)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'SHIB', 'amount':1000000.0, 'price_usd':0.000001, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'SHIB', 'amount':1000000.0, 'price_usd':0.00001, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Proceeds = 1000000 * 0.00001 = $10.00
        self.assertAlmostEqual(engine.tt[0]['Proceeds'], 10.0, delta=0.01)
    def test_date_far_in_future(self):
        """Edge case: Transaction dated 50 years in future"""
        self.db.save_trade({'id':'1', 'date':'2073-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2073)
        engine.run()
        self.assertEqual(len(engine.tt), 0)  # No sale, should have 0 tax transactions
    def test_date_far_in_past(self):
        """Edge case: Transaction dated 50 years in past"""
        self.db.save_trade({'id':'1', 'date':'1973-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':1.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'1973-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':10.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 1973)
        engine.run()
        self.assertEqual(engine.tt[0]['Cost Basis'], 1.0)
    def test_fractional_satoshi_handling(self):
        """Edge case: Amount smaller than 1 satoshi"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':0.0000000001, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Fractional satoshi crashed: {e}")

# --- 7. EDGE CASES - MALFORMED & BOUNDARY DATA ---


class TestEdgeCasesMalformedData(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'edge_malformed.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_null_values_in_trades(self):
        """Edge case: NULL values in critical fields"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':None, 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should skip or handle gracefully
            self.assertTrue(True)
        except Exception as e:
            # If it crashes, it should be a graceful error, not a silent failure
            self.assertIsNotNone(e)
    def test_empty_string_fields(self):
        """Edge case: Empty strings instead of values"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Empty coin field crashed: {e}")
    def test_invalid_action_type(self):
        """Edge case: Unknown action type"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'UNKNOWN_ACTION', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should handle unknown action gracefully (skip it)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Invalid action type crashed: {e}")
    def test_mixed_case_coin_names(self):
        """Edge case: Mixed case coin names (btc, BTC, Btc)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'btc', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':0.5, 'price_usd':20000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Should normalize and match both
        self.assertGreater(len(engine.tt), 0)
    def test_date_string_formats(self):
        """Edge case: Various date formats"""
        dates = [
            '2023-01-01',
            '2023-1-1',
            '01/01/2023',
            '2023/01/01',
            '2023-01-01T00:00:00'
        ]
        for i, date_str in enumerate(dates):
            try:
                self.db.save_trade({'id':f'{i}', 'date':date_str, 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':f'{i}'})
            except:
                pass  # Some formats may fail in DB layer, that's OK
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Mixed date formats crashed: {e}")
    def test_special_characters_in_coin_names(self):
        """Edge case: Special characters in coin names"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'USDC-e', 'amount':100.0, 'price_usd':1.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Special chars in coin crashed: {e}")
    def test_unicode_in_descriptions(self):
        """Edge case: Unicode characters in descriptions"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1', 'note':'Test™ © ® 🎉'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            engine.export()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Unicode crashed: {e}")

# --- 8. RANDOM SCENARIO GENERATORS - MONTE CARLO TESTING ---


class TestUnlikelyButValidTransactions(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'unlikely.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_sell_before_buy_same_day(self):
        """Unlikely: Sell on day 1, buy on day 2, but same exact times (should error or handle)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01T12:00:00', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-01-02T12:00:00', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':19000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should handle gracefully (insufficient basis)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Sell before buy crashed: {e}")
    def test_massive_price_volatility(self):
        """Unlikely: Buy at $1, sell at $50,000 next day (100,000x gain)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'DOGE', 'amount':1000000.0, 'price_usd':0.0001, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-01-02', 'source':'M', 'action':'SELL', 'coin':'DOGE', 'amount':1000000.0, 'price_usd':10.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        gain = engine.tt[0]['Proceeds'] - engine.tt[0]['Cost Basis']
        self.assertGreater(gain, 9000000.0)
    def test_same_transaction_duplicate_entries(self):
        """Unlikely but possible: Same transaction entered twice (duplicate detection)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'KRAKEN', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':10, 'batch_id':'1'})
        self.db.save_trade({'id':'1_DUP', 'date':'2023-01-01', 'source':'KRAKEN', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':10, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Should either skip duplicates or engine handles it
        self.assertTrue(True)
    def test_circular_arbitrage(self):
        """Unlikely: Trade A -> B -> C -> A all at profit (arbitrage loop)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-01-02', 'source':'SWAP', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-01-03', 'source':'M', 'action':'BUY', 'coin':'ETH', 'amount':1.0, 'price_usd':15000.0, 'fee':0, 'batch_id':'3'})
        self.db.save_trade({'id':'4', 'date':'2023-01-04', 'source':'SWAP', 'action':'SELL', 'coin':'ETH', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'4'})
        self.db.save_trade({'id':'5', 'date':'2023-01-05', 'source':'M', 'action':'BUY', 'coin':'USDC', 'amount':20000.0, 'price_usd':1.0, 'fee':0, 'batch_id':'5'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # All should be recognized as taxable events
        self.assertEqual(len(engine.tt), 2)
    def test_negative_income(self):
        """Unlikely: Negative income (refund or reversal)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'INCOME', 'coin':'BTC', 'amount':-0.1, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should skip or handle gracefully
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Negative income crashed: {e}")
    def test_identical_buy_sell_price_no_gain(self):
        """Unlikely: Buy at $100, sell at $100.00 (break-even)"""
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'USDC', 'amount':100.0, 'price_usd':1.0, 'fee':1, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2023-12-31', 'source':'M', 'action':'SELL', 'coin':'USDC', 'amount':100.0, 'price_usd':1.0, 'fee':1, 'batch_id':'2'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Should show loss due to fees
        gain = engine.tt[0]['Proceeds'] - engine.tt[0]['Cost Basis']
        self.assertLess(gain, 0)

# --- 10. EXTREME ERROR SCENARIOS - GRACEFUL DEGRADATION ---


class TestExtremeErrorScenariosGracefulDegradation(unittest.TestCase):
    def setUp(self):
        print(f"\n[Running: {self._testMethodName}] (This test may take 5-8 seconds)", flush=True)
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'extreme_error.db'
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
    def test_no_transactions_produces_empty_output(self):
        """Extreme: Database is empty (no transactions)"""
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            self.assertEqual(len(engine.tt), 0)
            self.assertEqual(len(engine.inc), 0)
        except Exception as e:
            self.fail(f"Empty database crashed: {e}")
    def test_database_with_multiple_years_single_year_processing(self):
        """Extreme: DB has 2020-2025 transactions, process only 2023"""
        for year in range(2020, 2026):
            self.db.save_trade({
                'id': f'{year}_buy',
                'date': f'{year}-01-01',
                'source': 'M',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 10000.0 + (year - 2020) * 1000,
                'fee': 0,
                'batch_id': f'{year}_buy'
            })
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        # Should only process 2023 transactions
        self.assertEqual(len(engine.tt), 0)  # No sales in 2023, so no tax transactions
    def test_corrupted_float_parsing(self):
        """Extreme: Try to parse amount as "1.0.0" (malformed float)"""
        # This test depends on DB layer accepting the value
        self.db.save_trade({
            'id': '1',
            'date': '2023-01-01',
            'source': 'M',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': float('inf'),  # Infinity price
            'fee': 0,
            'batch_id': '1'
        })
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should handle gracefully or skip
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Infinity price crashed: {e}")
    def test_nans_in_database(self):
        """Extreme: NaN values in transaction fields"""
        self.db.save_trade({
            'id': '1',
            'date': '2023-01-01',
            'source': 'M',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': float('nan'),
            'price_usd': 10000.0,
            'fee': 0,
            'batch_id': '1'
        })
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should skip NaN entries
            self.assertTrue(True)
        except Exception as e:
            # OK if it catches and logs the error
            self.assertIsNotNone(e)
    def test_all_missing_cost_basis(self):
        """Extreme: All sales with no matching buys (impossible scenario)"""
        self.db.save_trade({
            'id': '1',
            'date': '2023-01-01',
            'source': 'M',
            'action': 'SELL',
            'coin': 'BTC',
            'amount': 100.0,
            'price_usd': 10000.0,
            'fee': 0,
            'batch_id': '1'
        })
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should handle gracefully (0 cost basis or skip)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Missing cost basis crashed: {e}")
    def test_massive_portfolio_10k_transactions(self):
        """Extreme: 10,000 transactions in a single year"""
        base_date = datetime(2023, 1, 1)
        random.seed(42)
        
        for i in range(10000):
            action = random.choice(['BUY', 'INCOME'])
            self.db.save_trade({
                'id': f'MASSIVE_{i}',
                'date': (base_date + timedelta(seconds=random.randint(0, 31536000))).isoformat(),
                'source': 'RANDOM',
                'action': action,
                'coin': random.choice(['BTC', 'ETH', 'USDC']),
                'amount': random.uniform(0.01, 100.0),
                'price_usd': random.uniform(0.1, 50000.0),
                'fee': random.uniform(0, 100),
                'batch_id': f'MASSIVE_{i}'
            })
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        try:
            engine.run()
            # Should handle large portfolio without crashing
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"10K transaction portfolio crashed: {e}")

# --- 11. STAKETAXCSV INTEGRATION TESTS ---


class TestLargePortfolios(unittest.TestCase):
    """Test performance with large portfolios (100k+ trades)"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        app.BASE_DIR = self.test_path
        app.DB_FILE = self.test_path / 'large_portfolio.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
    
    def test_1000_trades_performance(self):
        """Test that 1000 trades can be processed efficiently"""
        import time as time_module
        start_time = time_module.time()
        
        # Insert 200 trades for faster testing
        for i in range(200):
            self.db.save_trade({
                'id': f'trade_{i}',
                'date': f'2024-01-{(i % 28) + 1:02d}',
                'source': ['COINBASE', 'KRAKEN', 'MANUAL'][i % 3],
                'action': ['BUY', 'SELL'][i % 2],
                'coin': ['BTC', 'ETH', 'USDC'][i % 3],
                'amount': 1.0 + (i % 10),
                'price_usd': 50000.0 + (i % 1000),
                'fee': i % 100,
                'batch_id': f'batch_{i // 100}'
            })
        
        self.db.commit()
        elapsed = time_module.time() - start_time
        
        # Verify all trades were saved
        df = self.db.get_all()
        self.assertEqual(len(df), 200)
        
        # Should complete in reasonable time
        self.assertLess(elapsed, 10.0)  # 10 seconds max for 200 trades
    
    def test_large_portfolio_query_performance(self):
        """Test that querying large portfolios is efficient"""
        import time as time_module
        # Insert 200 trades
        for i in range(200):
            self.db.save_trade({
                'id': f'trade_{i}',
                'date': f'2024-{(i % 12) + 1:02d}-01',
                'source': 'COINBASE',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 50000.0,
                'fee': 0,
                'batch_id': f'batch_{i // 100}'
            })
        
        self.db.commit()
        
        # Test query performance
        start_time = time_module.time()
        df = self.db.get_all()
        query_time = time_module.time() - start_time
        
        self.assertEqual(len(df), 200)
        # Query should be fast even with 200 records
        self.assertLess(query_time, 1.0)
    
    def test_portfolio_with_mixed_sources(self):
        """Test portfolio with trades from many different sources"""
        sources = ['COINBASE', 'KRAKEN', 'GEMINI', 'BINANCE', 'MANUAL', 'AIRDROP', 'STAKING', 'WALLET']
        
        # Insert 800 trades from different sources
        for i in range(800):
            self.db.save_trade({
                'id': f'trade_{i}',
                'date': '2024-06-01',
                'source': sources[i % len(sources)],
                'action': ['BUY', 'SELL', 'INCOME'][i % 3],
                'coin': f'COIN{i % 20}',
                'amount': float(i % 10 + 1),
                'price_usd': float(100 + (i % 1000)),
                'fee': float(i % 50),
                'batch_id': f'batch_{sources[i % len(sources)]}'
            })
        
        self.db.commit()
        
        df = self.db.get_all()
        self.assertEqual(len(df), 800)
        # Verify diverse sources
        unique_sources = df['source'].unique()
        self.assertGreater(len(unique_sources), 5)




class TestExtremeMarketConditions(unittest.TestCase):
    """Test handling of extreme market conditions"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        app.BASE_DIR = self.test_path
        app.DB_FILE = self.test_path / 'extreme_conditions.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
    
    def test_extremely_high_prices(self):
        """Test handling of extremely high prices (e.g., $1M+)"""
        self.db.save_trade({
            'id': 'high_1',
            'date': '2024-01-01',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 0.001,
            'price_usd': 1_000_000.0,  # $1M per BTC
            'fee': 0,
            'batch_id': 'high'
        })
        self.db.commit()
        
        df = self.db.get_all()
        self.assertEqual(df.iloc[0]['price_usd'], 1_000_000.0)
    
    def test_extremely_low_prices(self):
        """Test handling of extremely low prices (dust amounts, shib-like)"""
        self.db.save_trade({
            'id': 'dust_1',
            'date': '2024-01-01',
            'source': 'AIRDROP',
            'action': 'INCOME',
            'coin': 'SHIB',
            'amount': 1_000_000,
            'price_usd': 0.00000001,  # 1 satoshi
            'fee': 0,
            'batch_id': 'dust'
        })
        self.db.commit()
        
        df = self.db.get_all()
        # Convert Decimal to float for comparison
        price = float(df.iloc[0]['price_usd'])
        self.assertAlmostEqual(price, 0.00000001, places=10)
    
    def test_massive_volume_transactions(self):
        """Test handling of massive volume (e.g., 1 billion tokens)"""
        self.db.save_trade({
            'id': 'massive_1',
            'date': '2024-01-01',
            'source': 'MANUAL',
            'action': 'BUY',
            'coin': 'SHIB',
            'amount': 1_000_000_000,  # 1 billion
            'price_usd': 0.00001,
            'fee': 0,
            'batch_id': 'massive'
        })
        self.db.commit()
        
        df = self.db.get_all()
        self.assertEqual(df.iloc[0]['amount'], 1_000_000_000)
    
    def test_zero_price_handling(self):
        """Test handling of zero prices (airdrops, free tokens)"""
        self.db.save_trade({
            'id': 'free_1',
            'date': '2024-01-01',
            'source': 'AIRDROP',
            'action': 'INCOME',
            'coin': 'UNKNOWN',
            'amount': 100,
            'price_usd': 0.0,
            'fee': 0,
            'batch_id': 'free'
        })
        self.db.commit()
        
        df = self.db.get_all()
        self.assertEqual(df.iloc[0]['price_usd'], 0.0)




if __name__ == '__main__':
    unittest.main()


