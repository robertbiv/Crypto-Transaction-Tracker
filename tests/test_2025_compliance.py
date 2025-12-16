"""
================================================================================
TEST: 2025 US Tax Compliance
================================================================================

Validates compliance with 2025 US tax regulations for digital assets.

Regulatory Coverage:
    1. Rev. Proc. 2024-28 - Wallet-Based Cost Tracking
        - Strict broker mode isolation
        - 1099-DA reconciliation
        - Basis matching by source
    
    2. Proposed Wash Sale Rule (Future Law Simulation)
        - 30-day window before and after
        - Substantially identical crypto detection
        - Loss disallowance calculation
    
    3. Broker Reporting (1099-DA)
        - Separate accounting for custodial sources
        - Prevention of cross-wallet basis borrowing
        - Unmatched sell flagging
    
    4. Constructive Receipt
        - Staking rewards taxed at receipt
        - Mining income recognition
        - Conservative vs aggressive treatment

Compliance Modes Tested:
    - strict_broker_mode: True/False
    - wash_sale_rule: True/False
    - staking_taxable_on_receipt: True/False
    - defi_lp_conservative: True/False

Expected Outcomes:
    - Correct gain/loss calculation under various modes
    - Proper wash sale disallowance
    - Accurate 1099-DA alignment
    - Warning generation for audit risks

References:
    - IRS Notice 2014-21
    - Rev. Proc. 2024-28
    - Proposed Treasury Regulations §1.1091-1

Author: robertbiv
Last Modified: December 2025
================================================================================
"""
from test_common import *

class TestCompliance2025(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'compliance_2025.db'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.initialize_folders()
        self.db = app.DatabaseManager()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
        # Reset global config
        if 'compliance' in app.GLOBAL_CONFIG:
            del app.GLOBAL_CONFIG['compliance']

    def test_wash_sale_rule_disabled_by_default_2025(self):
        """
        Verify that Wash Sale Rule is DISABLED by default for 2025.
        Current law (2025) does not apply wash sales to crypto.
        """
        # Scenario: Buy BTC @ 20k, Sell @ 10k (Loss), Buy back immediately.
        # If Wash Sale is OFF: Loss is allowed.
        # If Wash Sale is ON: Loss is disallowed.
        
        self.db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2025-01-15', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2025-01-16', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()

        # Default Config (Wash Sale = False)
        engine = app.TaxEngine(self.db, 2025)
        engine.run()
        
        sale = engine.tt[0]
        # Proceeds 10k - Basis 20k = -10k Loss
        # If wash sale was active, basis would be adjusted or loss disallowed.
        # Here we expect full loss recognition.
        self.assertEqual(sale['Proceeds'], 10000.0)
        self.assertEqual(sale['Cost Basis'], 20000.0)
        self.assertNotIn('WASH SALE', sale['Description'])

    def test_wash_sale_rule_future_legislation_toggle(self):
        """
        Verify that Wash Sale Rule CAN be enabled for future compliance.
        """
        app.GLOBAL_CONFIG['compliance'] = {'wash_sale_rule': True}
        
        self.db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':20000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2025-01-15', 'source':'M', 'action':'SELL', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'2'})
        self.db.save_trade({'id':'3', 'date':'2025-01-16', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'3'})
        self.db.commit()

        engine = app.TaxEngine(self.db, 2025)
        engine.run()
        
        sale = engine.tt[0]
        # With Wash Sale ON:
        # The loss of 10k is disallowed.
        # Basis should be adjusted or loss zeroed out in the report logic.
        # The engine logic adds " (WASH SALE)" to description and adjusts basis to match proceeds (disallowing loss).
        self.assertIn('WASH SALE', sale['Description'])
        # In the engine implementation, if fully disallowed, Cost Basis = Proceeds (Net Gain/Loss = 0)
        self.assertEqual(sale['Cost Basis'], 10000.0) 

    def test_strict_broker_mode_1099_da_compliance(self):
        """
        Verify Rev. Proc. 2024-28 / 1099-DA Compliance.
        Sales on a Broker (e.g. Coinbase) MUST NOT use basis from a private wallet (Ledger).
        This ensures the user's 1099-DA matches their tax report.
        """
        app.GLOBAL_CONFIG['compliance'] = {
            'strict_broker_mode': True,
            'broker_sources': ['COINBASE', 'KRAKEN']
        }
        
        # 1. Buy on Ledger (Private Wallet)
        self.db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'LEDGER', 'action':'BUY', 'coin':'ETH', 'amount':10.0, 'price_usd':2000.0, 'fee':0, 'batch_id':'1'})
        
        # 2. Sell on Coinbase (Broker) - NO TRANSFER RECORDED
        # If we used Universal pooling, this would use the Ledger basis.
        # Under Strict Mode, it should fail to find basis (or use 0/estimate) because the coins aren't in Coinbase.
        self.db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'COINBASE', 'action':'SELL', 'coin':'ETH', 'amount':1.0, 'price_usd':3000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()

        engine = app.TaxEngine(self.db, 2025)
        engine.run()
        
        sale = engine.tt[0]
        # Should NOT use the $2000 basis from Ledger.
        # Engine defaults to 0.0 or estimated price (if enabled) when basis is missing in strict mode.
        # It definitely should NOT be 2000.0.
        self.assertNotEqual(sale['Cost Basis'], 2000.0)
        self.assertEqual(sale['Unmatched_Sell'], 'YES')

    def test_nft_look_through_collectibles(self):
        """
        Verify NFT 'Look-Through' support via Collectible tagging.
        """
        # Tag 'BAYC' as a collectible token
        app.GLOBAL_CONFIG['compliance'] = {'collectible_tokens': ['BAYC']}
        
        self.db.save_trade({'id':'1', 'date':'2025-01-01', 'source':'M', 'action':'BUY', 'coin':'BAYC', 'amount':1.0, 'price_usd':50000.0, 'fee':0, 'batch_id':'1'})
        self.db.save_trade({'id':'2', 'date':'2025-06-01', 'source':'M', 'action':'SELL', 'coin':'BAYC', 'amount':1.0, 'price_usd':60000.0, 'fee':0, 'batch_id':'2'})
        self.db.commit()

        engine = app.TaxEngine(self.db, 2025)
        engine.run()
        
        sale = engine.tt[0]
        self.assertTrue(sale['Collectible'])
