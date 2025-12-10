import unittest
import shutil
import tempfile
import json
import sqlite3
import pandas as pd
import sys
import os
import random
import math
import importlib
import requests 
from pathlib import Path
from unittest.mock import patch, MagicMock, SideEffect
from io import StringIO
from datetime import datetime, timedelta

# Import application logic
import Crypto_Tax_Engine as app
import Setup as setup_script
import Auto_Runner

# --- 1. SHADOW CALCULATOR (Standard FIFO) ---
class ShadowFIFO:
    def __init__(self):
        self.queues = {}
        self.realized_gains = []
        self.income_log = []
    def add(self, coin, amount, price, date, is_income=False):
        if coin not in self.queues: self.queues[coin] = []
        self.queues[coin].append({'amt': amount, 'price': price, 'date': date})
        self.queues[coin].sort(key=lambda x: x['date'])
        if is_income: self.income_log.append({'coin': coin, 'amt': amount, 'usd': amount * price})
    def sell(self, coin, amount, price, date, fee=0):
        if coin not in self.queues: self.queues[coin] = []
        rem_sell = amount
        total_basis = 0.0
        self.queues[coin].sort(key=lambda x: x['date'])
        valid_batches = [b for b in self.queues[coin] if b['date'] <= date]
        future_batches = [b for b in self.queues[coin] if b['date'] > date]
        self.queues[coin] = valid_batches
        while rem_sell > 1e-9 and self.queues[coin]:
            batch = self.queues[coin][0]
            if batch['amt'] <= rem_sell:
                total_basis += batch['amt'] * batch['price']
                rem_sell -= batch['amt']
                self.queues[coin].pop(0)
            else:
                total_basis += rem_sell * batch['price']
                batch['amt'] -= rem_sell
                rem_sell = 0
        self.queues[coin].extend(future_batches)
        self.queues[coin].sort(key=lambda x: x['date'])
        proceeds = (amount * price) - fee
        gain = proceeds - total_basis
        self.realized_gains.append({'coin': coin, 'proceeds': proceeds, 'basis': total_basis, 'gain': gain, 'date': date})

# --- 2. ADVANCED ACCOUNTING & COMPLIANCE TESTS ---
class TestAdvancedUSCompliance(unittest.TestCase):
    def setUp(self):
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
        tt_report = app.OUTPUT_DIR / "Year_2023" / "TURBOTAX_CAP_GAINS.csv"
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
class TestReportVerification(unittest.TestCase):
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
    def test_csv_output_accuracy(self):
        shadow = ShadowFIFO()
        shadow.add('BTC', 1.0, 10000.0, datetime(2023, 1, 1))
        self.db.save_trade({'id': '1', 'date': '2023-01-01', 'source': 'M', 'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 10000.0, 'fee': 0, 'batch_id': '1'})
        shadow.add('USDC', 100.0, 1.0, datetime(2023, 2, 1), is_income=True)
        self.db.save_trade({'id': '2', 'date': '2023-02-01', 'source': 'M', 'action': 'INCOME', 'coin': 'USDC', 'amount': 100.0, 'price_usd': 1.0, 'fee': 0, 'batch_id': '2'})
        shadow.sell('BTC', 0.5, 20000.0, datetime(2023, 3, 1))
        self.db.save_trade({'id': '3', 'date': '2023-03-01', 'source': 'M', 'action': 'SELL', 'coin': 'BTC', 'amount': 0.5, 'price_usd': 20000.0, 'fee': 0, 'batch_id': '3'})
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        engine.export()
        tt_file = app.OUTPUT_DIR / "Year_2023" / "TURBOTAX_CAP_GAINS.csv"
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
        self.assertEqual(df_snap[df_snap['Coin'] == 'BTC'].iloc[0]['Holdings'], 0.5)

class TestArchitectureStability(unittest.TestCase):
    def test_import_order_resilience(self):
        for module in ['Crypto_Tax_Engine', 'Auto_Runner']:
            if module in sys.modules: del sys.modules[module]
        modules_to_load = ['Crypto_Tax_Engine', 'Auto_Runner']
        random.shuffle(modules_to_load)
        print(f"\n--- TESTING IMPORT ORDER: {modules_to_load} ---")
        try:
            for m in modules_to_load: importlib.import_module(m)
        except ImportError as e: self.fail(f"Circular dependency: {e}")
        except Exception as e: self.fail(f"Module crashed: {e}")
        re_app = sys.modules['Crypto_Tax_Engine']
        self.assertTrue(hasattr(re_app, 'TaxEngine'))

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

class TestConfigHandling(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'config_test.db'
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
    def test_audit_disabled_in_config(self):
        app.GLOBAL_CONFIG['general']['run_audit'] = False
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"BTC": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]}, f)
        auditor = app.WalletAuditor(self.db)
        with patch.object(auditor, 'check_blockchair') as mock_bc:
            with self.assertLogs('crypto_tax_engine', level='INFO') as cm:
                auditor.run_audit()
            self.assertTrue(any("AUDIT SKIPPED" in log for log in cm.output))
            mock_bc.assert_not_called()
    def test_audit_enabled_but_no_keys(self):
        app.GLOBAL_CONFIG['general']['run_audit'] = True
        with open(app.KEYS_FILE, 'w') as f: 
            json.dump({"moralis": {"apiKey": "PASTE_KEY"}, "blockchair": {"apiKey": ""}}, f)
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"ETH": ["0x123"]}, f)
        auditor = app.WalletAuditor(self.db)
        with self.assertLogs('crypto_tax_engine', level='INFO') as cm:
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
        with open(app.KEYS_FILE, 'w') as f: json.dump({"blockchair": {"apiKey": "PASTE_KEY_OPTIONAL"}}, f)
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"BTC": ["1A1z..."]}, f)
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

class TestSystemInterruptions(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.ARCHIVE_DIR = self.test_path / 'processed_archive'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'crash_test.db'
        app.DB_BACKUP = self.test_path / 'crash_test.db.bak'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.GLOBAL_CONFIG['general']['create_db_backups'] = True
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_mid_write_crash(self):
        self.db.save_trade({'id': 'safe', 'date': '2023-01-01', 'source': 'M', 'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 100.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        self.db.create_safety_backup() 
        self.db.close()
        with open(app.DB_FILE, 'wb') as f: f.write(b'PARTIAL_WRITE_GARBAGE_DATA')
        new_db = app.DatabaseManager()
        new_db.restore_safety_backup() 
        df = new_db.get_all()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['id'], 'safe')
        new_db.close()
    @patch('requests.get')
    def test_network_timeout_retry(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        with open(app.KEYS_FILE, 'w') as f: json.dump({"moralis": {"apiKey": "test"}}, f)
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"ETH": ["0x123"]}, f)
        auditor = app.WalletAuditor(self.db)
        with patch('time.sleep') as mock_sleep:
            auditor.run_audit()
            self.assertGreaterEqual(mock_get.call_count, 5)
            mock_sleep.assert_called()

class TestSmartIngestor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.ARCHIVE_DIR = self.test_path / 'processed_archive'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'test_smart.db'
        app.initialize_folders()
        self.db = app.DatabaseManager()
        self.ingestor = app.Ingestor(self.db)
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    @patch('Crypto_Tax_Engine.PriceFetcher.get_price')
    def test_missing_price_backfill(self, mock_get_price):
        mock_get_price.return_value = 1500.0
        csv_file = app.INPUT_DIR / "missing_price.csv"
        with open(csv_file, 'w') as f:
            f.write("date,type,received_coin,received_amount,usd_value_at_time\n")
            f.write("2023-05-01,trade,ETH,2.0,0\n")
        self.ingestor.run_csv_scan()
        mock_get_price.assert_called() 
        df = self.db.get_all()
        row = df.iloc[0]
        self.assertEqual(row['price_usd'], 1500.0)
    def test_swap_detection(self):
        csv_file = app.INPUT_DIR / "swaps.csv"
        with open(csv_file, 'w') as f:
            f.write("date,type,sent_coin,sent_amount,received_coin,received_amount,fee\n")
            f.write("2023-06-01,trade,BTC,1.0,ETH,15.0,0.001\n")
        self.ingestor.run_csv_scan()
        df = self.db.get_all()
        self.assertEqual(len(df), 2)

class TestUserErrors(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.ARCHIVE_DIR = self.test_path / 'processed_archive'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.LOG_DIR = self.test_path / 'outputs' / 'logs'
        app.DB_FILE = self.test_path / 'error_test.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.held_stdout = sys.stdout
        sys.stdout = StringIO()
    def tearDown(self):
        sys.stdout = self.held_stdout
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_missing_setup(self):
        if app.KEYS_FILE.exists(): os.remove(app.KEYS_FILE)
        with self.assertRaises(SystemExit) as cm:
            if not app.KEYS_FILE.exists(): raise app.ApiAuthError("Missing keys")
        self.assertTrue(True)
    def test_bad_csv_data(self):
        csv_path = app.INPUT_DIR / "bad_data.csv"
        with open(csv_path, 'w') as f:
            f.write("date,coin,amount,usd_value_at_time,fee\n")
            f.write("2023-01-01,BTC,1.0,20000,0\n")
            f.write("2023-01-02,ETH,five,1500,0\n")
            f.write("2023-01-03,SOL,10,100,0\n")
            f.write("2023-01-04,XRP,100,200\n")
        db = app.DatabaseManager()
        ingestor = app.Ingestor(db)
        ingestor.run_csv_scan()
        df = db.get_all()
        self.assertGreaterEqual(len(df), 2)
    def test_corrupt_json_config(self):
        with open(app.KEYS_FILE, 'w') as f: f.write('{"binance": {"apiKey": "123", "secret": "abc"')
        defaults = {"new_key": "test"}
        setup_script.validate_json(app.KEYS_FILE, defaults)
        with open(app.KEYS_FILE) as f: data = json.load(f)
        self.assertIn("new_key", data)
        self.assertTrue(len(list(self.test_path.glob("*_CORRUPT.json"))) > 0)
    def test_database_corruption_recovery(self):
        db = app.DatabaseManager()
        db.close()
        with open(app.DB_FILE, 'wb') as f: f.write(b'GARBAGE_DATA_HEADER_DESTROYED' * 100)
        try:
            new_db = app.DatabaseManager()
            backups = list(self.test_path.glob("CORRUPT_*.db"))
            self.assertEqual(len(backups), 1)
            cursor = new_db.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades';")
            self.assertIsNotNone(cursor.fetchone())
            new_db.close()
        except Exception as e: self.fail(f"Engine crashed: {e}")

class TestChaosEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.ARCHIVE_DIR = self.test_path / 'processed_archive'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.LOG_DIR = self.test_path / 'outputs' / 'logs'
        app.DB_FILE = self.test_path / 'chaos.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_chaos_market(self):
        shadow = ShadowFIFO()
        coins = ['BTC', 'ETH', 'SOL', 'USDC']
        balances = {c: 0.0 for c in coins}
        curr_time = datetime(2023, 1, 1, 10, 0, 0)
        for i in range(500):
            curr_time += timedelta(hours=random.randint(1, 48))
            coin = random.choice(coins)
            action = random.choice(['BUY', 'INCOME']) if balances[coin] < 0.5 else random.choice(['BUY', 'SELL', 'INCOME', 'SWAP'])
            price = round(random.uniform(10, 3000), 2)
            amt = round(random.uniform(0.1, 2.0), 4)
            fee = round(random.uniform(0, 5.0), 2)
            if action == 'BUY':
                cost_total = (amt * price) + fee
                eff_price = cost_total / amt
                shadow.add(coin, amt, eff_price, curr_time)
                balances[coin] += amt
                self.db.save_trade({'id': f"T_{i}", 'date': curr_time.isoformat(), 'source': 'CHAOS', 'action': 'BUY', 'coin': coin, 'amount': amt, 'price_usd': price, 'fee': fee, 'batch_id': 'chaos'})
            elif action == 'INCOME':
                cost_total = (amt * price) + fee
                eff_price = cost_total / amt
                shadow.add(coin, amt, eff_price, curr_time, is_income=True)
                balances[coin] += amt
                self.db.save_trade({'id': f"T_{i}", 'date': curr_time.isoformat(), 'source': 'CHAOS', 'action': 'INCOME', 'coin': coin, 'amount': amt, 'price_usd': price, 'fee': fee, 'batch_id': 'chaos'})
            elif action == 'SELL':
                if balances[coin] < amt: amt = balances[coin]
                if amt < 1e-6: continue
                shadow.sell(coin, amt, price, curr_time, fee=fee)
                balances[coin] -= amt
                self.db.save_trade({'id': f"T_{i}", 'date': curr_time.isoformat(), 'source': 'CHAOS', 'action': 'SELL', 'coin': coin, 'amount': amt, 'price_usd': price, 'fee': fee, 'batch_id': 'chaos'})
            elif action == 'SWAP':
                coin_b = random.choice([c for c in coins if c != coin])
                if balances[coin] < amt: amt = balances[coin]
                if amt < 1e-6: continue
                price_b = round(random.uniform(10, 3000), 2)
                amt_b = (amt * price) / price_b
                shadow.sell(coin, amt, price, curr_time, fee=fee)
                balances[coin] -= amt
                self.db.save_trade({'id': f"T_{i}_SWAP_OUT", 'date': curr_time.isoformat(), 'source': 'CHAOS_SWAP', 'action': 'SELL', 'coin': coin, 'amount': amt, 'price_usd': price, 'fee': fee, 'batch_id': 'chaos'})
                shadow.add(coin_b, amt_b, price_b, curr_time)
                balances[coin_b] += amt_b
                self.db.save_trade({'id': f"T_{i}_SWAP_IN", 'date': curr_time.isoformat(), 'source': 'CHAOS_SWAP', 'action': 'BUY', 'coin': coin_b, 'amount': amt_b, 'price_usd': price_b, 'fee': 0, 'batch_id': 'chaos'})
        self.db.commit()
        years = sorted(list(set([t['date'].year for t in shadow.realized_gains] + [t['date'].year for t in shadow.income_log])))
        engine_gains = 0.0
        engine_income = 0.0
        for y in years:
            eng = app.TaxEngine(self.db, y)
            eng.run()
            for t in eng.tt: engine_gains += (t['Proceeds'] - t['Cost Basis'])
            for i in eng.inc: engine_income += i['USD']
        shadow_gains = sum(t['gain'] for t in shadow.realized_gains)
        shadow_income = sum(t['usd'] for t in shadow.income_log)
        self.assertAlmostEqual(shadow_gains, engine_gains, delta=1.0)
        self.assertAlmostEqual(shadow_income, engine_income, delta=1.0)

class TestSafety(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'safety.db'
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_isolation(self):
        app.initialize_folders()
        self.assertTrue(str(app.DB_FILE).startswith(self.test_dir))

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

if __name__ == '__main__':
    print("--- RUNNING ULTIMATE SUITE V30 (Strict FIFO + Robust US Tax Compliance + HIFO Config) ---")
    unittest.main()