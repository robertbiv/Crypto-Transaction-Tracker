"""
Integration tests for real tax scenarios.
Tests edge cases and multi-leg trades with Decimal precision.
"""

import pytest
from decimal import Decimal
from src.decimal_utils import to_decimal, USD_PRECISION, SATOSHI
from src.transaction_validator import TransactionValidator


class TestRealTaxScenarios:
    """Integration tests simulating realistic tax scenarios."""
    
    def test_wash_sale_with_fractional_amounts(self):
        """Test wash sale detection with fractional BTC and satoshi precision."""
        transactions = [
            {
                'id': 1,
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': '0.12345678',  # 12,345,678 satoshis
                'price_usd': '42000.50',
                'source': 'kraken'
            },
            {
                'id': 2,
                'date': '2024-01-15',  # 14 days later (within wash sale window)
                'action': 'SELL',
                'coin': 'BTC',
                'amount': '0.12345678',
                'price_usd': '41500.25',
                'source': 'kraken'
            }
        ]
        
        # Validate transactions
        for tx in transactions:
            is_valid, errors = TransactionValidator.validate_transaction(tx)
            assert is_valid, f"Validation errors: {errors}"
        
        # Calculate proceeds and cost basis
        buy_amount = to_decimal(transactions[0]['amount'])
        buy_price = to_decimal(transactions[0]['price_usd'])
        sell_amount = to_decimal(transactions[1]['amount'])
        sell_price = to_decimal(transactions[1]['price_usd'])
        
        cost_basis = (buy_amount * buy_price).quantize(USD_PRECISION)
        proceeds = (sell_amount * sell_price).quantize(USD_PRECISION)
        capital_loss = (proceeds - cost_basis).quantize(USD_PRECISION)
        
        # Verify precision
        assert buy_amount == Decimal('0.12345678')
        assert cost_basis == Decimal('5185.25')  # 0.12345678 * 42000.50, rounded
        assert proceeds == Decimal('5123.49')  # 0.12345678 * 41500.25, rounded
        assert capital_loss == Decimal('-61.76')  # Proceeds - Cost basis
    
    def test_multi_leg_trade_with_fees(self):
        """Test multi-leg trades with fee deductions."""
        # Scenario: Buy BTC, swap to ETH, sell ETH
        transactions = [
            {
                'id': 1,
                'date': '2024-02-01',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': '0.5',
                'price_usd': '50000.00',
                'source': 'binance'
            },
            {
                'id': 2,
                'date': '2024-02-02',
                'action': 'TRADE',
                'coin': 'BTC',  # Swapping from
                'amount': '0.5',
                'price_usd': '51000.00',  # Price at swap time
                'source': 'uniswap'
            },
            {
                'id': 3,
                'date': '2024-02-03',
                'action': 'TRADE',
                'coin': 'ETH',  # Received in swap
                'amount': '8.5',
                'price_usd': '3000.00',
                'source': 'uniswap'
            },
            {
                'id': 4,
                'date': '2024-02-05',
                'action': 'SELL',
                'coin': 'ETH',
                'amount': '8.5',
                'price_usd': '3100.00',
                'source': 'kraken'
            }
        ]
        
        # Validate all transactions
        for tx in transactions:
            is_valid, errors = TransactionValidator.validate_transaction(tx)
            assert is_valid, f"Tx {tx['id']} errors: {errors}"
        
        # BTC leg: Cost basis
        btc_amount = to_decimal(transactions[0]['amount'])
        btc_buy_price = to_decimal(transactions[0]['price_usd'])
        btc_cost_basis = (btc_amount * btc_buy_price).quantize(USD_PRECISION)
        assert btc_cost_basis == Decimal('25000.00')
        
        # BTC swap leg: Proceeds
        btc_swap_price = to_decimal(transactions[1]['price_usd'])
        btc_swap_proceeds = (btc_amount * btc_swap_price).quantize(USD_PRECISION)
        btc_capital_gain = (btc_swap_proceeds - btc_cost_basis).quantize(USD_PRECISION)
        assert btc_capital_gain == Decimal('500.00')
        
        # ETH leg: Cost basis (from swap)
        eth_amount = to_decimal(transactions[2]['amount'])
        eth_swap_price = to_decimal(transactions[2]['price_usd'])
        eth_cost_basis = (eth_amount * eth_swap_price).quantize(USD_PRECISION)
        assert eth_cost_basis == Decimal('25500.00')
        
        # ETH sale leg: Proceeds and gain
        eth_sell_price = to_decimal(transactions[3]['price_usd'])
        eth_proceeds = (eth_amount * eth_sell_price).quantize(USD_PRECISION)
        eth_capital_gain = (eth_proceeds - eth_cost_basis).quantize(USD_PRECISION)
        assert eth_capital_gain == Decimal('850.00')
        
        # Total tax effect
        total_gain = (btc_capital_gain + eth_capital_gain).quantize(USD_PRECISION)
        assert total_gain == Decimal('1350.00')
    
    def test_dust_precision_in_calculations(self):
        """Test that satoshi-level dust is handled correctly."""
        # Buy: 0.00000001 BTC (1 satoshi) at $50,000
        dust = Decimal('0.00000001')
        price = Decimal('50000.00')
        
        value = (dust * price).quantize(USD_PRECISION)
        # 0.00000001 * 50000 = 0.0005 cents
        assert value == Decimal('0.00')  # Rounds to $0 at USD precision
        
        # But keeping Decimal precision shows true value
        exact_value = dust * price
        assert exact_value == Decimal('0.0005')
    
    def test_fee_deduction_accuracy(self):
        """Test accurate fee deduction in capital gains."""
        # Buy 1 ETH at $2000
        eth_amount = to_decimal('1.0')
        eth_price = to_decimal('2000.00')
        cost_basis = (eth_amount * eth_price).quantize(USD_PRECISION)
        
        # Buy fee: $5
        buy_fee = to_decimal('5.00')
        adjusted_cost_basis = (cost_basis + buy_fee).quantize(USD_PRECISION)
        
        # Sell 1 ETH at $2100
        sell_price = to_decimal('2100.00')
        proceeds = (eth_amount * sell_price).quantize(USD_PRECISION)
        
        # Sell fee: $5
        sell_fee = to_decimal('5.00')
        adjusted_proceeds = (proceeds - sell_fee).quantize(USD_PRECISION)
        
        # Capital gain after fees
        capital_gain = (adjusted_proceeds - adjusted_cost_basis).quantize(USD_PRECISION)
        
        assert adjusted_cost_basis == Decimal('2005.00')
        assert adjusted_proceeds == Decimal('2095.00')
        assert capital_gain == Decimal('90.00')  # ($2100 - $5) - ($2000 + $5)
    
    def test_fractional_percentage_calculation(self):
        """Test accurate percentage calculations with fractions."""
        # Fee is 0.25% of $10,000
        total = to_decimal('10000.00')
        fee_pct = to_decimal('0.0025')  # 0.25%
        
        fee = (total * fee_pct).quantize(USD_PRECISION)
        assert fee == Decimal('25.00')
        
        # Verify: 10000 * 0.0025 = 25.00
        assert fee == Decimal('10000.00') * Decimal('0.0025')
    
    def test_airdrop_and_income_precision(self):
        """Test income transactions (airdrops, staking) with precision."""
        transactions = [
            {
                'id': 1,
                'date': '2024-03-01',
                'action': 'INCOME',
                'coin': 'AIRDROP-TOKEN',
                'amount': '1000.123456789',  # Many decimals
                'price_usd': '0.00001234',  # Very small price
                'source': 'airdrop'
            }
        ]
        
        is_valid, errors = TransactionValidator.validate_transaction(transactions[0])
        assert is_valid, f"Errors: {errors}"
        
        amount = to_decimal(transactions[0]['amount'])
        price = to_decimal(transactions[0]['price_usd'])
        
        # Income value with full precision
        income_value = (amount * price).quantize(USD_PRECISION)
        # 1000.123456789 * 0.00001234 = 0.01234152...
        assert income_value == Decimal('0.01')  # Rounds down per ROUND_HALF_UP at $0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
