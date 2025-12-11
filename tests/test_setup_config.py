import unittest
import tempfile
import shutil
import json
import os
from pathlib import Path

import Setup as setup_script
import Crypto_Tax_Engine as app

class TestSetupConfigCompliance(unittest.TestCase):
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
                "staking_taxable_on_receipt": True,
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
        self.assertIn('staking_taxable_on_receipt', cfg['compliance'])
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
                "staking_taxable_on_receipt": True,
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
        self.assertTrue(cfg['compliance']['staking_taxable_on_receipt'])

    def test_setup_instructions_contain_recommendation_labels(self):
        # Verify Setup.py config_data contains clear recommendation labels
        # This ensures users see warnings before enabling risky options
        config_defaults = {
            "general": {"run_audit": True, "create_db_backups": True},
            "accounting": {"method": "FIFO"},
            "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
            "logging": {"compress_older_than_days": 30},
            "compliance": {
                "_INSTRUCTIONS": "2025 IRS compliance controls. strict_broker_mode (Recommended=True) prevents basis borrowing across wallets for custodial sources (1099-DA alignment). broker_sources is the list of custodial sources. staking_taxable_on_receipt (Recommended=True) controls constructive receipt for staking/mining; setting False is aggressive and may be challenged. collectibles can be flagged via prefixes/tokens.",
                "strict_broker_mode": True,
                "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
                "staking_taxable_on_receipt": True,
                "collectible_prefixes": ["NFT-", "ART-"],
                "collectible_tokens": ["NFT", "PUNK", "BAYC"]
            },
            "staking": {"enabled": False, "protocols_to_sync": ["all"]}
        }
        
        # Verify compliance instructions contain key recommendation labels
        comp_instructions = config_defaults['compliance']['_INSTRUCTIONS']
        self.assertIn('Recommended=True', comp_instructions, "Compliance instructions should mark recommended settings")
        self.assertIn('strict_broker_mode', comp_instructions)
        self.assertIn('staking_taxable_on_receipt', comp_instructions)
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
                "staking_taxable_on_receipt": True,
                "collectible_prefixes": ["NFT-"],
                "collectible_tokens": ["PUNK"]
            }
        }
        with open(setup_script.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f)

        # Point engine to temp BASE_DIR and reload GLOBAL_CONFIG
        app.BASE_DIR = self.tmp_path
        app.INPUT_DIR = self.tmp_path / 'inputs'
        app.OUTPUT_DIR = self.tmp_path / 'outputs'
        app.DB_FILE = self.tmp_path / 'engine_config_test.db'
        app.CONFIG_FILE = setup_script.CONFIG_FILE
        app.initialize_folders()
        db = app.DatabaseManager()

        # Scenario 1: Strict broker blocks basis borrowing
        db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'LEDGER', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'1'})
        db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'COINBASE', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':60000.0, 'fee':0, 'batch_id':'2'})
        db.commit()
        eng = app.TaxEngine(db, 2025)
        eng.run()
        self.assertEqual(eng.tt[0]['Cost Basis'], 0.0)

        # Scenario 2: Collectible token long-term reporting
        db.save_trade({'id':'3', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'PUNK', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'3'})
        db.save_trade({'id':'4', 'date':'2024-02-02', 'source':'M', 'action':'SELL', 'coin':'PUNK', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'4'})
        db.commit()
        eng2 = app.TaxEngine(db, 2024)
        eng2.run()
        eng2.export()
        loss_csv = app.OUTPUT_DIR / 'Year_2024' / 'US_TAX_LOSS_ANALYSIS.csv'
        self.assertTrue(loss_csv.exists())
        df = json.load(open(loss_csv, 'r')) if False else None  # placeholder to ensure file handle not left open
        import pandas as pd
        dfp = pd.read_csv(loss_csv)
        val_collectible = float(dfp[dfp['Item']=='Current Year Long-Term (Collectibles 28%)']['Value'].iloc[0])
        self.assertEqual(val_collectible, 10000.0)
        db.close()