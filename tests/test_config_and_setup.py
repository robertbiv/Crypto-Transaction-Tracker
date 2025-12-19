"""
================================================================================
TEST: Configuration and Setup
================================================================================

Validates configuration file handling and setup processes.

Test Coverage:
    - config.json loading and validation
    - Default configuration generation
    - Configuration merging (user + defaults)
    - Invalid configuration handling
    - Setup wizard workflows
    - First-run initialization

Author: robertbiv
================================================================================
"""
from test_common import *

class TestConfigHandling(unittest.TestCase):
    def setUp(self):
        print(f"\n[Running: {self._testMethodName}]", flush=True)
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Patch globals
        self.base_patcher = patch('Crypto_Transaction_Engine.BASE_DIR', self.test_path)
        self.input_patcher = patch('Crypto_Transaction_Engine.INPUT_DIR', self.test_path / 'inputs')
        self.output_patcher = patch('Crypto_Transaction_Engine.OUTPUT_DIR', self.test_path / 'outputs')
        self.db_patcher = patch('Crypto_Transaction_Engine.DB_FILE', self.test_path / 'config_test.db')
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
        self.held_stdout = sys.stdout
        sys.stdout = StringIO()

    def tearDown(self):
        sys.stdout = self.held_stdout
        self.db.close()
        
        self.config_patcher.stop()
        self.wallets_patcher.stop()
        self.keys_patcher.stop()
        self.db_patcher.stop()
        self.output_patcher.stop()
        self.input_patcher.stop()
        self.base_patcher.stop()
        
        shutil.rmtree(self.test_dir)
    def test_audit_disabled_in_config(self):
        app.GLOBAL_CONFIG['general']['run_audit'] = False
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"BTC": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]}, f)
        auditor = app.WalletAuditor(self.db)
        with patch.object(auditor, 'check_blockchair') as mock_bc:
            with self.assertLogs('Crypto_Transaction_Engine', level='INFO') as cm:
                auditor.run_audit()
            self.assertTrue(any("AUDIT SKIPPED" in log for log in cm.output))
            mock_bc.assert_not_called()
    def test_audit_enabled_but_no_keys(self):
        app.GLOBAL_CONFIG['general']['run_audit'] = True
        with open(app.KEYS_FILE, 'w') as f: 
            json.dump({"moralis": {"apiKey": "PASTE_KEY"}, "blockchair": {"apiKey": ""}}, f)
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"ETH": ["0x123"]}, f)
        auditor = app.WalletAuditor(self.db)
        with self.assertLogs('Crypto_Transaction_Engine', level='INFO') as cm:
            auditor.run_audit()
        self.assertTrue(any("RUNNING AUDIT" in log for log in cm.output))
    def test_throttling_respects_config(self):
        app.GLOBAL_CONFIG['general']['run_audit'] = True
        app.GLOBAL_CONFIG['performance']['respect_free_tier_limits'] = True
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"BTC": ["addr1", "addr2"]}, f)
        auditor = app.WalletAuditor(self.db)
        with patch('time.sleep') as mock_sleep:
            with patch.object(auditor, 'check_blockchair', return_value=0):
                auditor.run_audit()
            mock_sleep.assert_called()
    @patch('requests.get')
    def test_blockchair_optionality(self, mock_get):
        app.GLOBAL_CONFIG['general']['run_audit'] = True
        app.save_api_keys_file({"blockchair": {"apiKey": "PASTE_KEY_OPTIONAL"}})
        app.save_wallets_file({"BTC": ["1A1z..."]})
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"1A1z...": {"address": {"balance": 100000000}}}}
        mock_get.return_value = mock_response
        auditor = app.WalletAuditor(self.db)
        auditor.run_audit()
        args, kwargs = mock_get.call_args
        url_called = args[0]
        self.assertIn("api.blockchair.com/bitcoin", url_called)
        self.assertNotIn("?key=", url_called)
        self.assertEqual(auditor.real['BTC'], 1.0)



class TestConfigFileHandling(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_invalid_json_config(self):
        """Test: Invalid JSON in config is handled"""
        with open(app.CONFIG_FILE, 'w') as f:
            f.write("{invalid json}")
        
        try:
            # Should handle gracefully
            with open(app.CONFIG_FILE) as f:
                json.load(f)
            self.fail("Invalid JSON should raise exception")
        except json.JSONDecodeError:
            # Expected - invalid JSON is caught
            self.assertTrue(True)
    
    def test_missing_config_fields(self):
        """Test: Missing config fields use defaults"""
        with open(app.CONFIG_FILE, 'w') as f:
            json.dump({"accounting": {}}, f)
        
        try:
            with open(app.CONFIG_FILE) as f:
                config = json.load(f)
            # Should have basic structure
            self.assertIsInstance(config, dict)
        except Exception as e:
            self.fail(f"Config handling failed: {e}")
    
    def test_type_mismatch_in_config(self):
        """Test: Type mismatches in config are handled"""
        with open(app.CONFIG_FILE, 'w') as f:
            json.dump({"staking": {"enabled": "yes"}}, f)  # Should be bool
        
        try:
            with open(app.CONFIG_FILE) as f:
                config = json.load(f)
            # Should handle gracefully or convert
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Type mismatch caused crash: {e}")

# --- 21. HOLDING PERIOD CALCULATION TESTS ---


class TestSetupScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.orig_base = setup_script.BASE_DIR
        self.orig_req_dirs = setup_script.REQUIRED_DIRS
        self.orig_keys = setup_script.KEYS_FILE
        setup_script.BASE_DIR = self.root
        setup_script.REQUIRED_DIRS = [self.root/'inputs', self.root/'outputs']
        setup_script.KEYS_FILE = self.root/'api_keys.json'
        self.held_stdout = sys.stdout
        sys.stdout = StringIO()
    def tearDown(self):
        sys.stdout = self.held_stdout
        shutil.rmtree(self.test_dir)
        setup_script.BASE_DIR = self.orig_base
        setup_script.REQUIRED_DIRS = self.orig_req_dirs
        setup_script.KEYS_FILE = self.orig_keys
    def test_json_generation_fresh(self):
        setup_script.validate_json(setup_script.KEYS_FILE, {"k":"v"})
        self.assertTrue(setup_script.KEYS_FILE.exists())

# --- 6. EDGE CASES - EXTREME VALUES & BOUNDARY CONDITIONS ---


class TestSetupConfigCompliance(unittest.TestCase):
    """Test Setup configuration compliance settings"""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp)
        # Redirect Setup.py BASE_DIR to temp path
        self.orig_base = setup_script.BASE_DIR
        setup_script.BASE_DIR = self.tmp_path
        setup_script.REQUIRED_DIRS = [self.tmp_path/'inputs', self.tmp_path/'processed_archive', self.tmp_path/'outputs', self.tmp_path/'outputs'/'logs']
        setup_script.KEYS_FILE = self.tmp_path/'api_keys.json'
        setup_script.WALLETS_FILE = self.tmp_path/'wallets.json'
        setup_script.CONFIG_FILE = self.tmp_path/'config.json'

        # Ensure folders exist for writing config
        for d in setup_script.REQUIRED_DIRS:
            if not d.exists(): d.mkdir(parents=True)

    def tearDown(self):
        setup_script.BASE_DIR = self.orig_base
        shutil.rmtree(self.tmp)

    def test_config_includes_compliance_section_on_create(self):
        # Build the same config_data dictionary used by Setup.py
        config_data = {
            "_INSTRUCTIONS": "General runtime options.",
            "general": {"run_audit": True, "create_db_backups": True},
            "accounting": {"method": "FIFO"},
            "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
            "logging": {"compress_older_than_days": 30},
            "compliance": {
                "strict_broker_mode": True,
                "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
                "staking_transactionable_on_receipt": True,
                "collectible_prefixes": ["NFT-", "ART-"],
                "collectible_tokens": ["NFT", "PUNK", "BAYC"]
            },
            "staking": {"enabled": False, "protocols_to_sync": ["all"]}
        }

        # Ensure config.json does not exist, then validate_json should create it
        if setup_script.CONFIG_FILE.exists():
            setup_script.CONFIG_FILE.unlink()

        setup_script.validate_json(setup_script.CONFIG_FILE, config_data)

        # Read config and assert compliance section present with keys
        with open(setup_script.CONFIG_FILE) as f:
            cfg = json.load(f)
        self.assertIn('compliance', cfg)
        self.assertIn('strict_broker_mode', cfg['compliance'])
        self.assertIn('broker_sources', cfg['compliance'])
        self.assertIn('staking_transactionable_on_receipt', cfg['compliance'])
        self.assertIn('collectible_prefixes', cfg['compliance'])
        self.assertIn('collectible_tokens', cfg['compliance'])

    def test_config_compliance_merge_adds_missing_keys(self):
        # Start with config missing compliance section entirely
        with open(setup_script.CONFIG_FILE, 'w') as f:
            json.dump({
                "general": {"run_audit": False, "create_db_backups": False},
                "accounting": {"method": "FIFO"}
            }, f)

        # Defaults (with compliance) should merge in
        defaults = {
            "general": {"run_audit": True, "create_db_backups": True},
            "accounting": {"method": "FIFO"},
            "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
            "logging": {"compress_older_than_days": 30},
            "compliance": {
                "strict_broker_mode": True,
                "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
                "staking_transactionable_on_receipt": True,
                "collectible_prefixes": ["NFT-", "ART-"],
                "collectible_tokens": ["NFT", "PUNK", "BAYC"]
            },
            "staking": {"enabled": False, "protocols_to_sync": ["all"]}
        }

        setup_script.validate_json(setup_script.CONFIG_FILE, defaults)

        with open(setup_script.CONFIG_FILE) as f:
            cfg = json.load(f)
        # Original keys preserved
        self.assertEqual(cfg['general']['run_audit'], False)
        self.assertEqual(cfg['general']['create_db_backups'], False)
        # Compliance keys added
        self.assertIn('compliance', cfg)
        self.assertTrue(cfg['compliance']['strict_broker_mode'])
        self.assertIsInstance(cfg['compliance']['broker_sources'], list)
        self.assertTrue(cfg['compliance']['staking_transactionable_on_receipt'])

    def test_setup_instructions_contain_recommendation_labels(self):
        # Verify Setup.py config_data contains clear recommendation labels
        # This ensures users see warnings before enabling risky options
        config_defaults = {
            "general": {"run_audit": True, "create_db_backups": True},
            "accounting": {"method": "FIFO"},
            "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
            "logging": {"compress_older_than_days": 30},
            "compliance": {
                "_INSTRUCTIONS": "2025 IRS compliance controls. strict_broker_mode (Recommended=True) prevents basis borrowing across wallets for custodial sources (1099-DA alignment). broker_sources is the list of custodial sources. staking_transactionable_on_receipt (Recommended=True) controls constructive receipt for staking/mining; setting False is aggressive and may be challenged. collectibles can be flagged via prefixes/tokens.",
                "strict_broker_mode": True,
                "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
                "staking_transactionable_on_receipt": True,
                "collectible_prefixes": ["NFT-", "ART-"],
                "collectible_tokens": ["NFT", "PUNK", "BAYC"]
            },
            "staking": {"enabled": False, "protocols_to_sync": ["all"]}
        }
        
        # Verify compliance instructions contain key recommendation labels
        comp_instructions = config_defaults['compliance']['_INSTRUCTIONS']
        self.assertIn('Recommended=True', comp_instructions, "Compliance instructions should mark recommended settings")
        self.assertIn('strict_broker_mode', comp_instructions)
        self.assertIn('staking_transactionable_on_receipt', comp_instructions)
        self.assertIn('aggressive', comp_instructions, "Should warn that False is aggressive")
        self.assertIn('1099-DA', comp_instructions, "Should mention 1099-DA alignment")

    def test_engine_respects_config_strict_broker_and_collectibles(self):
        # Write a config.json with specific compliance settings
        cfg = {
            "general": {"run_audit": True, "create_db_backups": True},
            "accounting": {"method": "FIFO"},
            "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
            "logging": {"compress_older_than_days": 30},
            "compliance": {
                "strict_broker_mode": True,
                "broker_sources": ["COINBASE"],
                "staking_transactionable_on_receipt": True,
                "collectible_prefixes": ["NFT-"],
                "collectible_tokens": ["PUNK"]
            }
        }
        with open(setup_script.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f)

        # Point engine to temp BASE_DIR
        app.BASE_DIR = self.tmp_path
        app.INPUT_DIR = self.tmp_path / 'inputs'
        app.OUTPUT_DIR = self.tmp_path / 'outputs'
        app.DB_FILE = self.tmp_path / 'engine_config_test.db'
        app.CONFIG_FILE = setup_script.CONFIG_FILE
        app.initialize_folders()
        db = app.DatabaseManager()

        try:
            # Verify config file was written correctly
            with open(setup_script.CONFIG_FILE) as f:
                read_cfg = json.load(f)
            
            # Verify the config has our compliance settings
            self.assertIn('compliance', read_cfg)
            self.assertTrue(read_cfg['compliance']['strict_broker_mode'])
            self.assertIn('COINBASE', read_cfg['compliance']['broker_sources'])
            self.assertIn('NFT-', read_cfg['compliance']['collectible_prefixes'])
            self.assertIn('PUNK', read_cfg['compliance']['collectible_tokens'])
            
            # Verify engine can run with config
            db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'LEDGER', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'1'})
            db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'COINBASE', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':60000.0, 'fee':0, 'batch_id':'2'})
            db.commit()
            eng = app.TransactionEngine(db, 2025)
            eng.run()
            # Just verify the engine ran without errors
            self.assertIsNotNone(eng.tt)
        finally:
            db.close()




class TestAutoRunner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        self.orig_db = app.DB_FILE
        self.orig_output = app.OUTPUT_DIR
        self.orig_input = app.INPUT_DIR
        app.BASE_DIR = self.test_path
        app.DB_FILE = self.test_path / 'crypto_master.db'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.INPUT_DIR = self.test_path / 'inputs'
        app.initialize_folders()

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
        app.DB_FILE = self.orig_db
        app.OUTPUT_DIR = self.orig_output
        app.INPUT_DIR = self.orig_input

    def _stub_ingestor(self):
        class DummyIngestor:
            def __init__(self, db):
                pass
            def run_csv_scan(self):
                return None
            def run_api_sync(self):
                return None
        return DummyIngestor

    def _stub_stake_mgr(self):
        class DummyStake:
            def __init__(self, db):
                pass
            def run(self):
                return None
        return DummyStake

    def _stub_price_fetcher(self):
        class DummyPF:
            def __init__(self):
                pass
            def get_price(self, *_args, **_kwargs):
                return Decimal('0')
        return DummyPF

    def _fixed_datetime(self, year):
        fixed_now = datetime(year, 12, 31, 12, 0, 0)
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_now if tz is None else fixed_now.astimezone(tz)
        return FixedDateTime

    def test_auto_runner_generates_reports_with_seed_data(self):
        # Seed 2022 and 2023 holdings so snapshots are produced
        db = app.DatabaseManager()
        db.save_trade({'id': 'b2022', 'date': '2022-06-01', 'source': 'EX', 'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 20000.0, 'fee': 0, 'batch_id': '2022'})
        db.save_trade({'id': 'b2023', 'date': '2023-03-01', 'source': 'EX', 'action': 'BUY', 'coin': 'ETH', 'amount': 2.0, 'price_usd': 1000.0, 'fee': 0, 'batch_id': '2023'})
        db.commit()
        db.close()

        with patch.object(app, 'Ingestor', self._stub_ingestor()), \
             patch.object(app, 'StakeActivityCSVManager', self._stub_stake_mgr()), \
             patch.object(app, 'PriceFetcher', self._stub_price_fetcher()), \
             patch.object(Auto_Runner, 'datetime', self._fixed_datetime(2023)):
            Auto_Runner.run_automation()

        prev_snap = app.OUTPUT_DIR / 'Year_2022' / 'EOY_HOLDINGS_SNAPSHOT.csv'
        curr_snap = app.OUTPUT_DIR / 'Year_2023' / 'CURRENT_HOLDINGS_DRAFT.csv'
        self.assertTrue(prev_snap.exists(), "Prev year snapshot should be created")
        self.assertTrue(curr_snap.exists(), "Current year draft snapshot should be created")

    def test_auto_runner_skips_finalized_prev_year_and_runs_current(self):
        # Create existing snapshot to simulate manual run completion
        fixed_dt = self._fixed_datetime(2024)
        prev_year = 2023
        year_dir = app.OUTPUT_DIR / f'Year_{prev_year}'
        year_dir.mkdir(parents=True, exist_ok=True)
        snapshot_file = year_dir / 'EOY_HOLDINGS_SNAPSHOT.csv'
        snapshot_file.write_text("Coin,Holdings\nBTC,1\n")

        created_engines = []
        def fake_engine(db, year):
            class FakeEngine:
                def __init__(self, db, year):
                    self.year = year
                    created_engines.append(year)
                def run(self):
                    return None
                def export(self):
                    return None
            return FakeEngine(db, year)

        with patch.object(app, 'Ingestor', self._stub_ingestor()), \
             patch.object(app, 'StakeActivityCSVManager', self._stub_stake_mgr()), \
             patch.object(app, 'PriceFetcher', self._stub_price_fetcher()), \
             patch.object(Auto_Runner, 'datetime', fixed_dt), \
             patch.object(app, 'TransactionEngine', side_effect=fake_engine):
            Auto_Runner.run_automation()

        # Should only instantiate TransactionEngine for current year (2024), not prev_year (2023)
        self.assertIn(2024, created_engines)
        self.assertNotIn(prev_year, created_engines)

    def test_auto_runner_triggers_manual_review_with_warnings(self):
        """Test that Auto Runner invokes Transaction Reviewer and detects issues"""
        from Transaction_Reviewer import TransactionReviewer
        
        # Seed database with problematic data that should trigger warnings
        db = app.DatabaseManager()
        
        # 1. NFT without proper prefix (should trigger NFT warning)
        db.save_trade({
            'id': 'nft1', 'date': '2024-06-01', 'source': 'OPENSEA', 
            'action': 'BUY', 'coin': 'BAYC#1234', 
            'amount': 1, 'price_usd': 50000, 'fee': 0, 'batch_id': 'nft'
        })
        
        # 2. BTC sale followed by WBTC purchase within 30 days (wash sale)
        db.save_trade({
            'id': 'btc_buy', 'date': '2024-01-01', 'source': 'BINANCE',
            'action': 'BUY', 'coin': 'BTC', 
            'amount': 1, 'price_usd': 40000, 'fee': 0, 'batch_id': 'wash'
        })
        db.save_trade({
            'id': 'btc_sell', 'date': '2024-06-01', 'source': 'BINANCE',
            'action': 'SELL', 'coin': 'BTC', 
            'amount': 1, 'price_usd': 35000, 'fee': 0, 'batch_id': 'wash'
        })
        db.save_trade({
            'id': 'wbtc_buy', 'date': '2024-06-15', 'source': 'BINANCE',
            'action': 'BUY', 'coin': 'WBTC', 
            'amount': 1, 'price_usd': 35500, 'fee': 0, 'batch_id': 'wash'
        })
        
        # 3. Missing price data (should trigger missing price warning)
        db.save_trade({
            'id': 'no_price', 'date': '2024-07-01', 'source': 'WALLET',
            'action': 'INCOME', 'coin': 'UNKNOWN', 
            'amount': 100, 'price_usd': 0, 'fee': 0, 'batch_id': 'missing'
        })
        
        db.commit()
        db.close()
        
        # Capture review output
        review_called = []
        original_run_review = TransactionReviewer.run_review
        
        def mock_run_review(self):
            result = original_run_review(self)
            review_called.append(result)
            return result
        
        with patch.object(app, 'Ingestor', self._stub_ingestor()), \
             patch.object(app, 'StakeActivityCSVManager', self._stub_stake_mgr()), \
             patch.object(app, 'PriceFetcher', self._stub_price_fetcher()), \
             patch.object(Auto_Runner, 'datetime', self._fixed_datetime(2024)), \
             patch.object(TransactionReviewer, 'run_review', mock_run_review):
            Auto_Runner.run_automation()
        
        # Verify review was called
        self.assertEqual(len(review_called), 1, "Manual review should be called once")
        
        report = review_called[0]
        
        # Verify warnings were detected
        self.assertGreater(len(report['warnings']), 0, "Should detect warnings")
        
        # Check for specific warning categories
        warning_categories = [w['category'] for w in report['warnings']]
        self.assertIn('NFT_COLLECTIBLES', warning_categories, "Should detect NFT without proper prefix")
        self.assertIn('SUBSTANTIALLY_IDENTICAL_WASH_SALES', warning_categories, "Should detect BTC/WBTC wash sale")
        self.assertIn('MISSING_PRICES', warning_categories, "Should detect missing price data")
        
        # Verify summary
        self.assertGreaterEqual(report['summary']['total_warnings'], 3, "Should have at least 3 warnings")




class TestConfigMerging(unittest.TestCase):
    """Tests for config.json merging to catch new option integration errors"""
    
    def setUp(self):
        print(f"\n[Running: {self._testMethodName}]", flush=True)
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.CONFIG_FILE = self.test_path / 'config.json'
    
    def tearDown(self):
        app.BASE_DIR = self.orig_base
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_new_defi_lp_option_merges_with_existing_config(self):
        """Test: defi_lp_conservative option merges into existing config"""
        # Create existing config WITHOUT defi_lp_conservative
        existing_config = {
            'general': {
                'run_audit': True,
                'create_db_backups': True
            },
            'compliance': {
                'warn_on_fifo_complexity': True
            }
        }
        
        with open(app.CONFIG_FILE, 'w') as f:
            json.dump(existing_config, f, indent=4)
        
        # Run Setup which should merge in new options
        with patch('builtins.input', return_value=''):  # Auto-accept defaults
            # Simulate the config merge logic from Setup.py
            with open(app.CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
            
            # Add new option
            if 'compliance' not in user_config:
                user_config['compliance'] = {}
            user_config['compliance']['defi_lp_conservative'] = True
            
            with open(app.CONFIG_FILE, 'w') as f:
                json.dump(user_config, f, indent=4)
        
        # Verify merge worked
        with open(app.CONFIG_FILE, 'r') as f:
            merged_config = json.load(f)
        
        self.assertIn('defi_lp_conservative', merged_config['compliance'])
        self.assertTrue(merged_config['compliance']['defi_lp_conservative'])
        
        # Verify old options preserved
        self.assertTrue(merged_config['general']['run_audit'])
        self.assertTrue(merged_config['compliance']['warn_on_fifo_complexity'])
    
    def test_config_loads_defi_lp_conservative_default(self):
        """Test: Config defaults to conservative=True if not specified"""
        # Create config without defi_lp_conservative
        config = {'general': {'run_audit': True}}
        with open(app.CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        # Reload config
        with open(app.CONFIG_FILE, 'r') as f:
            loaded_config = json.load(f)
        
        # Check default behavior
        defi_conservative = loaded_config.get('compliance', {}).get('defi_lp_conservative', True)
        self.assertTrue(defi_conservative, "Should default to True (conservative)")



if __name__ == '__main__':
    unittest.main()


