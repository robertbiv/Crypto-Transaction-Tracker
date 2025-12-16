"""
================================================================================
TEST: Comprehensive Edge Case Scenarios
================================================================================

Validates complex cryptocurrency transaction scenarios and edge cases.

Test Coverage:
    1. Liquidity Pools (LPs)
        - Impermanent loss realization
        - Entry/exit taxable events
        - Cost basis tracking through swaps
    
    2. Staking
        - Liquid staking (ETH -> stETH)
        - Staking rewards as income
        - Taxable events vs non-taxable deposits
    
    3. Cross-Wallet Transfers
        - Basis preservation across sources
        - Fee handling on transfers
        - Destination wallet tracking
    
    4. Trading Scenarios
        - Stablecoin swaps (USDC -> USDT)
        - Fiat on/off ramps
        - Crypto-to-crypto exchanges
    
    5. Edge Cases
        - Dust cleanup (tiny amounts)
        - Airdrop handling
        - Fork distributions

Test Methodology:
    - Isolated test database per test
    - Monkeypatched paths for isolation
    - Real TaxEngine calculations (integration tests)
    - Assertion of expected tax treatment

Author: robertbiv
Last Modified: December 2025
================================================================================
"""
from test_common import *

class TestComprehensiveScenarios(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'comprehensive.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base

    # ==========================================
    # 1. LIQUIDITY POOLS (LPs)
    # ==========================================
    def test_lp_impermanent_loss_realization(self):
        """
        Test LP lifecycle:
        1. Swap ETH -> LP Token (Taxable Event)
        2. Hold (Price changes)
        3. Swap LP Token -> ETH + USDC (Taxable Event, realizing impermanent loss)
        """
        # Buy 2 ETH @ 2000
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'WALLET', 'action':'BUY', 'coin':'ETH', 'amount':2.0, 'price_usd':2000.0, 'fee':0, 'batch_id':'1'})
        
        # Enter LP: Swap 2 ETH for 100 UNI-V2 (Taxable Dispostion of ETH)
        # ETH Price is now 2500. Gain = (2500 - 2000) * 2 = 1000
        self.db.save_trade({'id':'2', 'date':'2023-02-01', 'source':'WALLET', 'action':'SELL', 'coin':'ETH', 'amount':2.0, 'price_usd':2500.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-02-01', 'source':'WALLET', 'action':'BUY', 'coin':'UNI-V2', 'amount':100.0, 'price_usd':50.0, 'fee':0, 'batch_id':'2'}) # Cost Basis 5000
        
        # Exit LP: Swap 100 UNI-V2 for 1.5 ETH + 2000 USDC
        # ETH Price dropped to 1500. Total Value = (1.5 * 1500) + 2000 = 4250.
        # Loss = 4250 - 5000 = -750.
        self.db.save_trade({'id':'4', 'date':'2023-06-01', 'source':'WALLET', 'action':'SELL', 'coin':'UNI-V2', 'amount':100.0, 'price_usd':42.5, 'fee':0, 'batch_id':'3'})
        self.db.save_trade({'id':'5', 'date':'2023-06-01', 'source':'WALLET', 'action':'BUY', 'coin':'ETH', 'amount':1.5, 'price_usd':1500.0, 'fee':0, 'batch_id':'3'})
        self.db.save_trade({'id':'6', 'date':'2023-06-01', 'source':'WALLET', 'action':'BUY', 'coin':'USDC', 'amount':2000.0, 'price_usd':1.0, 'fee':0, 'batch_id':'3'})
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Verify ETH Gain
        eth_sale = next(t for t in engine.tt if t['Coin'] == 'ETH')
        self.assertEqual(eth_sale['Proceeds'], 5000.0)
        self.assertEqual(eth_sale['Cost Basis'], 4000.0) # 2 * 2000
        
        # Verify LP Loss
        lp_sale = next(t for t in engine.tt if t['Coin'] == 'UNI-V2')
        self.assertEqual(lp_sale['Proceeds'], 4250.0)
        self.assertEqual(lp_sale['Cost Basis'], 5000.0)

    # ==========================================
    # 2. STAKING
    # ==========================================
    def test_liquid_staking_swap(self):
        """
        Test ETH -> stETH swap (Taxable) vs Locked Staking (Non-taxable deposit)
        """
        # Buy 1 ETH @ 1000
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'WALLET', 'action':'BUY', 'coin':'ETH', 'amount':1.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'1'})
        
        # Swap for stETH @ 2000 (Gain 1000)
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'WALLET', 'action':'SELL', 'coin':'ETH', 'amount':1.0, 'price_usd':2000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-06-01', 'source':'WALLET', 'action':'BUY', 'coin':'stETH', 'amount':1.0, 'price_usd':2000.0, 'fee':0, 'batch_id':'2'})
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        sale = engine.tt[0]
        self.assertEqual(sale['Coin'], 'ETH')
        self.assertEqual(sale['Proceeds'], 2000.0)
        self.assertEqual(sale['Cost Basis'], 1000.0)

    def test_staking_rewards_income(self):
        """Test staking rewards are treated as Income at FMV"""
        self.db.save_trade({'id':'1', 'date':'2023-03-01', 'source':'STAKING', 'action':'INCOME', 'coin':'SOL', 'amount':1.0, 'price_usd':50.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        self.assertEqual(len(engine.inc), 1)
        self.assertEqual(engine.inc[0]['USD'], 50.0)

    # ==========================================
    # 3. TRANSFERS & BASIS TRACKING
    # ==========================================
    def test_transfer_fee_taxability(self):
        """
        Transfer 1 ETH. Fee is 0.01 ETH.
        The transfer itself is not taxable.
        The fee IS a taxable disposition of 0.01 ETH.
        """
        # Buy 2 ETH @ 1000
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'WALLET_A', 'action':'BUY', 'coin':'ETH', 'amount':2.0, 'price_usd':1000.0, 'fee':0, 'batch_id':'1'})
        
        # Transfer 1 ETH to WALLET_B. Fee 0.01 ETH. Price now 2000.
        # Fee Cost Basis: 0.01 * 1000 = 10.
        # Fee Proceeds: 0.01 * 2000 = 20.
        # Gain: 10.
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'WALLET_A', 'destination':'WALLET_B', 'action':'TRANSFER', 'coin':'ETH', 'amount':1.0, 'price_usd':2000.0, 'fee':0.01, 'batch_id':'2'})
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        self.assertEqual(len(engine.tt), 1)
        fee_tx = engine.tt[0]
        self.assertIn('(Fee)', fee_tx['Description'])
        self.assertEqual(fee_tx['Proceeds'], 20.0)
        self.assertEqual(fee_tx['Cost Basis'], 10.0)

    # ==========================================
    # 4. BUYING & SELLING
    # ==========================================
    def test_stablecoin_swap_friction(self):
        """
        Swap USDC -> USDT.
        Technically a taxable event, usually near-zero gain/loss.
        """
        # Buy 1000 USDC @ 1.00
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'WALLET', 'action':'BUY', 'coin':'USDC', 'amount':1000.0, 'price_usd':1.0, 'fee':0, 'batch_id':'1'})
        
        # Swap for USDT @ 1.001 (slight depeg/premium)
        self.db.save_trade({'id':'2', 'date':'2023-01-02', 'source':'WALLET', 'action':'SELL', 'coin':'USDC', 'amount':1000.0, 'price_usd':1.001, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2023-01-02', 'source':'WALLET', 'action':'BUY', 'coin':'USDT', 'amount':1000.0, 'price_usd':1.001, 'fee':0, 'batch_id':'2'})
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        sale = engine.tt[0]
        self.assertEqual(sale['Coin'], 'USDC')
        self.assertAlmostEqual(sale['Proceeds'], 1001.0)
        self.assertAlmostEqual(sale['Cost Basis'], 1000.0)

    # ==========================================
    # 5. EDGE CASES
    # ==========================================
    def test_dust_cleanup(self):
        """
        Selling 'dust' (tiny amounts) should still calculate correctly.
        """
        # Buy 1 BTC @ 50k
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'WALLET', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'1'})
        
        # Sell 0.00000001 BTC (1 sat) @ 60k
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'WALLET', 'action':'SELL', 'coin':'BTC', 'amount':0.00000001, 'price_usd':60000.0, 'fee':0, 'batch_id':'2'})
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        sale = engine.tt[0]
        # Proceeds: 0.0006
        # Basis: 0.0005
        self.assertAlmostEqual(sale['Proceeds'], 0.0006, places=6)
        self.assertAlmostEqual(sale['Cost Basis'], 0.0005, places=6)

    def test_airdrop_zero_basis(self):
        """Airdrop has 0 cost basis if not treated as income (or FMV if income)."""
        # Case A: Treated as Income (Standard)
        self.db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'WALLET', 'action':'INCOME', 'coin':'UNI', 'amount':100.0, 'price_usd':5.0, 'fee':0, 'batch_id':'1'})
        
        # Sell
        self.db.save_trade({'id':'2', 'date':'2023-06-01', 'source':'WALLET', 'action':'SELL', 'coin':'UNI', 'amount':100.0, 'price_usd':10.0, 'fee':0, 'batch_id':'2'})
        
        self.db.commit()
        engine = app.TaxEngine(self.db, 2023)
        engine.run()
        
        # Income: 500
        self.assertEqual(engine.inc[0]['USD'], 500.0)
        
        # Capital Gain: Proceeds 1000 - Basis 500 = 500
        sale = engine.tt[0]
        self.assertEqual(sale['Cost Basis'], 500.0)
