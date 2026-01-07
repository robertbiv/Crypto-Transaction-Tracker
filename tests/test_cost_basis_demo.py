"""
Demonstration test for cost basis preservation across wallet transfers.
This test validates that cost basis is based on ORIGINAL PURCHASE DATE,
not the date when crypto is transferred to a new wallet.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.database import DatabaseManager
from src.core.engine import TransactionEngine
import tempfile
import os

def test_cost_basis_follows_original_purchase_date():
    """
    Demonstrates that cost basis is determined by the ORIGINAL PURCHASE DATE,
    not the wallet transfer date - matching the IRS requirements.
    
    Scenario:
    1. Buy 1 BTC on Jan 1, 2021 for $10,000 (on Binance)
    2. Transfer to Coinbase on Jan 31, 2024
    3. Sell on Nov 22, 2024 for $50,000
    
    Expected behavior:
    - Cost basis: $10,000 (from 2021 purchase, NOT the 2024 transfer)
    - Holding period: Long-term (based on 2021 acquisition date)
    - Capital gain: $40,000 (long-term)
    
    This matches the real user scenario described in the IRS guidance.
    """
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = DatabaseManager(db_path)
        
        # Step 1: Purchase BTC on Binance in 2021
        print("\n" + "="*70)
        print("SCENARIO: Testing Cost Basis Preservation Across Wallet Transfers")
        print("="*70)
        print("\n1. Jan 1, 2021: Purchase 1 BTC on Binance for $10,000")
        db.save_trade({
            'id': '1',
            'date': '2021-01-01',
            'source': 'BINANCE',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 10000.0,
            'fee': 0,
            'batch_id': '1'
        })
        
        # Step 2: Transfer BTC from Binance to Coinbase in 2024
        print("2. Jan 31, 2024: Transfer 1 BTC from Binance to Coinbase")
        db.save_trade({
            'id': '2',
            'date': '2024-01-31',
            'source': 'BINANCE',
            'destination': 'COINBASE',
            'action': 'TRANSFER',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 0,  # Transfer price irrelevant - not a taxable event
            'fee': 0,
            'batch_id': '2'
        })
        
        # Step 3: Sell BTC on Coinbase in 2024
        print("3. Nov 22, 2024: Sell 1 BTC on Coinbase for $50,000")
        db.save_trade({
            'id': '3',
            'date': '2024-11-22',
            'source': 'COINBASE',
            'action': 'SELL',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000.0,
            'fee': 0,
            'batch_id': '3'
        })
        
        db.commit()
        
        # Run the transaction engine
        print("\nProcessing transactions...")
        engine = TransactionEngine(db, 2024)
        engine.run()
        
        # Verify results
        assert len(engine.tt) == 1, "Should have exactly 1 taxable transaction"
        
        sale = engine.tt[0]
        
        print("\n" + "="*70)
        print("RESULTS:")
        print("="*70)
        print(f"Sale Date: {sale['Date Sold']}")
        print(f"Acquisition Date: {sale['Date Acquired']}")
        print(f"Proceeds: ${sale['Proceeds']:,.2f}")
        print(f"Cost Basis: ${sale['Cost Basis']:,.2f}")
        print(f"Capital Gain: ${sale['Proceeds'] - sale['Cost Basis']:,.2f}")
        print(f"Holding Period: {sale['Term']}")
        print(f"Source Wallet: {sale['Source']}")
        
        # Assertions
        print("\n" + "="*70)
        print("VERIFICATION:")
        print("="*70)
        
        # Cost basis should be from 2021 purchase ($10,000), NOT the 2024 transfer
        assert abs(sale['Cost Basis'] - 10000.0) < 0.01, \
            f"Cost basis should be $10,000 (2021 purchase price), got ${sale['Cost Basis']}"
        print("✓ Cost basis is $10,000 (from original 2021 purchase)")
        
        # Proceeds should be $50,000
        assert abs(sale['Proceeds'] - 50000.0) < 0.01, \
            f"Proceeds should be $50,000, got ${sale['Proceeds']}"
        print("✓ Proceeds are $50,000")
        
        # Should be Long-term (more than 1 year from 2021 acquisition)
        assert sale['Term'] == 'Long', \
            f"Holding period should be 'Long' (acquired 2021), got '{sale['Term']}'"
        print("✓ Holding period is Long-term (based on 2021 acquisition)")
        
        # Acquisition date should be from 2021, NOT 2024
        assert '2021' in sale['Date Acquired'], \
            f"Acquisition date should be from 2021 (original purchase), got {sale['Date Acquired']}"
        print(f"✓ Acquisition date is {sale['Date Acquired']} (original purchase date)")
        
        # Capital gain calculation
        capital_gain = sale['Proceeds'] - sale['Cost Basis']
        assert abs(capital_gain - 40000.0) < 0.01, \
            f"Capital gain should be $40,000, got ${capital_gain}"
        print(f"✓ Capital gain is ${capital_gain:,.2f}")
        
        print("\n" + "="*70)
        print("✅ ALL CHECKS PASSED")
        print("="*70)
        print("\nKey Findings:")
        print("• Cost basis is based on ORIGINAL PURCHASE DATE (2021)")
        print("• Transfer date (2024) does NOT affect cost basis")
        print("• Holding period starts from ORIGINAL ACQUISITION (2021)")
        print("• System correctly implements IRS Revenue Procedure 2024-28")
        print("• This prevents incorrect short-term vs long-term classification")
        print("\nThis matches the IRS requirement that cost basis and acquisition")
        print("date 'travel with' the cryptocurrency across wallet transfers.")
        print("="*70 + "\n")
        
    finally:
        # Cleanup
        db.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == '__main__':
    test_cost_basis_follows_original_purchase_date()
    print("\n✅ Test completed successfully!")
